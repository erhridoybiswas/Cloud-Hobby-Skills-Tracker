"""
File / object storage routes.

POST   /api/files/upload
GET    /api/files
GET    /api/files/raw/<storage_key>
DELETE /api/files/<file_id>

The database stores only metadata (key, size, content-type). The bytes
live in the configured object storage backend.

Transaction-safety note: if the storage upload succeeds but the database
insert fails, we compensate by deleting the just-uploaded object — this
is the "saga / compensating transaction" pattern for a system that spans
two different storage engines.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, g, request, send_file

from analytics.progress_service import now_iso
from backend.middleware.auth_middleware import optional_auth, require_auth
from backend.utils.ids import new_id
from backend.utils.responses import created, error, forbidden, not_found, ok
from backend.utils.validators import validate_upload
from cloud.database_service import execute, query_all, query_one
from cloud.storage_service import StorageError, get_storage

files_bp = Blueprint("files", __name__, url_prefix="/api")


# ---------------------------------------------------------------------
@files_bp.post("/files/upload")
@require_auth
def upload_file():
    """
    Upload a file to cloud object storage.

    Multipart form fields:
      file       (required) — the binary payload
      folder     (optional) — profile | skills | posts | misc
      is_public  (optional) — "1"/"true" to make it publicly readable
    """
    if "file" not in request.files:
        return error("No file part named 'file' was found in the request.", 400)

    upload = request.files["file"]

    allowed = current_app.config["ALLOWED_EXTENSIONS"]
    max_bytes = current_app.config["MAX_CONTENT_LENGTH"]

    valid, message = validate_upload(upload, allowed, max_bytes)
    if not valid:
        return error(message, 415 if "not allowed" in message else 400)

    folder = (request.form.get("folder") or "misc").strip().lower()
    if folder not in current_app.config["ALLOWED_FOLDERS"]:
        folder = "misc"

    is_public = (request.form.get("is_public") or "").lower() in {"1", "true", "yes"}

    storage = get_storage()

    # Step 1 — put the bytes in object storage
    try:
        stored = storage.upload(upload, g.user_id, folder, is_public)
    except StorageError as exc:
        current_app.logger.error("Storage upload failed: %s", exc)
        return error("File storage is temporarily unavailable. Please retry.", 503)

    # Step 2 — record the metadata in the database
    file_id = new_id("file")
    try:
        execute(
            """
            INSERT INTO files (file_id, user_id, original_name, storage_key,
                               content_type, size_bytes, folder, is_public, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id, g.user_id, stored["original_name"], stored["storage_key"],
                stored["content_type"], stored["size_bytes"], folder,
                stored["is_public"], now_iso(),
            ),
        )
    except Exception as exc:
        # Compensating action: the DB write failed, so remove the orphan object
        current_app.logger.exception("DB insert failed after upload: %s", exc)
        try:
            storage.delete(stored["storage_key"])
        except Exception:
            current_app.logger.error("Cleanup of orphan object also failed.")
        return error("Could not save file metadata. The upload was rolled back.", 500)

    record = query_one("SELECT * FROM files WHERE file_id = ?", (file_id,))
    record["url"] = storage.url_for(record["storage_key"], bool(record["is_public"]))
    return created({"file": record})


# ---------------------------------------------------------------------
@files_bp.get("/files")
@require_auth
def list_files():
    """List the caller's uploaded files, newest first."""
    rows = query_all(
        "SELECT * FROM files WHERE user_id = ? ORDER BY created_at DESC",
        (g.user_id,),
    )
    storage = get_storage()
    for row in rows:
        row["url"] = storage.url_for(row["storage_key"], bool(row["is_public"]))
    return ok({"files": rows, "count": len(rows)})


# ---------------------------------------------------------------------
@files_bp.get("/files/raw/<path:storage_key>")
@optional_auth
def serve_raw_file(storage_key: str):
    """
    Stream a stored object.

    Authorization:
      * public files  -> anyone (including anonymous visitors)
      * private files -> only the owner

    In cloud mode with S3 you would instead redirect to a presigned URL
    so the bytes never pass through your API server.
    """
    record = query_one("SELECT * FROM files WHERE storage_key = ?", (storage_key,))
    if not record:
        return not_found("File")

    if not record["is_public"] and record["user_id"] != g.user_id:
        return forbidden("This file is private.")

    storage = get_storage()
    if not storage.exists(storage_key):
        return not_found("File object")

    if hasattr(storage, "open_stream"):
        return send_file(
            storage.open_stream(storage_key),
            mimetype=record["content_type"],
            download_name=record["original_name"],
            max_age=3600,
        )

    # Cloud backends: hand off to a signed URL
    return ok({"url": storage.url_for(storage_key, bool(record["is_public"]))})


# ---------------------------------------------------------------------
@files_bp.delete("/files/<file_id>")
@require_auth
def delete_file(file_id: str):
    """Delete a file the caller owns, from BOTH the database and object storage."""
    record = query_one("SELECT * FROM files WHERE file_id = ?", (file_id,))
    if not record:
        return not_found("File")
    if record["user_id"] != g.user_id:
        return forbidden("You can only delete your own files.")

    storage = get_storage()

    # Object storage first: if this fails we keep the DB row so the user
    # can retry, rather than losing the reference to an orphaned object.
    try:
        storage.delete(record["storage_key"])
    except Exception as exc:
        current_app.logger.error("Failed to delete object %s: %s", record["storage_key"], exc)
        return error("Could not delete the stored object. Please retry.", 503)

    execute("DELETE FROM files WHERE file_id = ? AND user_id = ?", (file_id, g.user_id))
    return ok({"message": "File deleted from storage and database."})