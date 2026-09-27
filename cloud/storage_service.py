"""
Cloud Object Storage Service
============================

The database stores only METADATA about a file (key, size, content-type).
The actual bytes live in object storage.

Local mode  -> writes to backend/uploads/
Cloud mode  -> S3 / Supabase Storage / GCS (same method signatures)

Storage key convention:
    users/<user_id>/<folder>/<uuid>.<ext>
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional
from uuid import uuid4

from flask import current_app


class StorageError(Exception):
    """Raised when an object-storage operation fails."""


class BaseStorageService:
    """Interface every storage backend must implement."""

    def upload(self, file_storage, user_id: str, folder: str = "misc", is_public: bool = False) -> dict:
        raise NotImplementedError

    def delete(self, storage_key: str) -> bool:
        raise NotImplementedError

    def url_for(self, storage_key: str, is_public: bool = True) -> str:
        raise NotImplementedError

    def exists(self, storage_key: str) -> bool:
        raise NotImplementedError


# ---------------------------------------------------------------------
# Local disk implementation (used for development & testing)
# ---------------------------------------------------------------------
class LocalStorageService(BaseStorageService):
    """Stores objects as files on the local filesystem."""

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # -- internal -----------------------------------------------------
    def _build_key(self, user_id: str, folder: str, filename: str) -> str:
        ext = Path(filename or "").suffix.lower() or ".bin"
        return f"users/{user_id}/{folder}/{uuid4().hex}{ext}"

    def _abs_path(self, storage_key: str) -> Path:
        """Resolve a key to an absolute path, blocking path traversal."""
        candidate = (self.root / storage_key).resolve()
        if not str(candidate).startswith(str(self.root)):
            raise StorageError("Invalid storage key (path traversal blocked)")
        return candidate

    # -- interface ----------------------------------------------------
    def upload(self, file_storage, user_id: str, folder: str = "misc", is_public: bool = False) -> dict:
        key = self._build_key(user_id, folder, file_storage.filename)
        destination = self._abs_path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            file_storage.save(destination)
        except OSError as exc:
            raise StorageError(f"Failed to write file: {exc}") from exc

        return {
            "storage_key": key,
            "size_bytes": destination.stat().st_size,
            "content_type": file_storage.mimetype or "application/octet-stream",
            "original_name": file_storage.filename,
            "is_public": 1 if is_public else 0,
        }

    def delete(self, storage_key: str) -> bool:
        path = self._abs_path(storage_key)
        if path.exists():
            path.unlink()
            return True
        return False

    def url_for(self, storage_key: str, is_public: bool = True) -> str:
        # Served by the /api/files/raw/<key> route in file_routes.py
        return f"/api/files/raw/{storage_key}"

    def exists(self, storage_key: str) -> bool:
        return self._abs_path(storage_key).exists()

    def open_stream(self, storage_key: str):
        """Return a readable binary stream (used by the download route)."""
        return open(self._abs_path(storage_key), "rb")


# ---------------------------------------------------------------------
# Cloud implementations (stubs — enable when you have credentials)
# ---------------------------------------------------------------------
class S3StorageService(BaseStorageService):
    """
    Amazon S3 / any S3-compatible storage (Cloudflare R2, MinIO, Backblaze B2).

    Enable with:  STORAGE_BACKEND=s3
    Requires:     pip install boto3
    """

    def __init__(self, bucket: str, region: str):
        import boto3  # imported lazily so local mode needs no boto3
        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region)

    def upload(self, file_storage, user_id: str, folder: str = "misc", is_public: bool = False) -> dict:
        ext = Path(file_storage.filename or "").suffix.lower() or ".bin"
        key = f"users/{user_id}/{folder}/{uuid4().hex}{ext}"
        file_storage.stream.seek(0, 2)
        size = file_storage.stream.tell()
        file_storage.stream.seek(0)

        extra = {"ContentType": file_storage.mimetype or "application/octet-stream"}
        if is_public:
            extra["ACL"] = "public-read"
        self.client.upload_fileobj(file_storage.stream, self.bucket, key, ExtraArgs=extra)

        return {
            "storage_key": key,
            "size_bytes": size,
            "content_type": file_storage.mimetype or "application/octet-stream",
            "original_name": file_storage.filename,
            "is_public": 1 if is_public else 0,
        }

    def delete(self, storage_key: str) -> bool:
        self.client.delete_object(Bucket=self.bucket, Key=storage_key)
        return True

    def url_for(self, storage_key: str, is_public: bool = True) -> str:
        if is_public:
            return f"https://{self.bucket}.s3.amazonaws.com/{storage_key}"
        # Signed URL valid for 15 minutes — secure temporary access
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": storage_key},
            ExpiresIn=900,
        )

    def exists(self, storage_key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=storage_key)
            return True
        except Exception:
            return False


class SupabaseStorageService(BaseStorageService):
    """
    Supabase Storage (free tier: 1 GB).

    Enable with:  STORAGE_BACKEND=supabase
    Requires:     pip install supabase
    """

    def __init__(self, url: str, service_key: str, bucket: str):
        from supabase import create_client
        self.bucket = bucket
        self.client = create_client(url, service_key)

    def upload(self, file_storage, user_id: str, folder: str = "misc", is_public: bool = False) -> dict:
        ext = Path(file_storage.filename or "").suffix.lower() or ".bin"
        key = f"users/{user_id}/{folder}/{uuid4().hex}{ext}"
        data = file_storage.read()
        self.client.storage.from_(self.bucket).upload(
            path=key,
            file=data,
            file_options={"content-type": file_storage.mimetype or "application/octet-stream"},
        )
        return {
            "storage_key": key,
            "size_bytes": len(data),
            "content_type": file_storage.mimetype or "application/octet-stream",
            "original_name": file_storage.filename,
            "is_public": 1 if is_public else 0,
        }

    def delete(self, storage_key: str) -> bool:
        self.client.storage.from_(self.bucket).remove([storage_key])
        return True

    def url_for(self, storage_key: str, is_public: bool = True) -> str:
        if is_public:
            return self.client.storage.from_(self.bucket).get_public_url(storage_key)
        return self.client.storage.from_(self.bucket).create_signed_url(storage_key, 900)["signedURL"]

    def exists(self, storage_key: str) -> bool:
        try:
            self.client.storage.from_(self.bucket).list(path=str(Path(storage_key).parent))
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------
def get_storage() -> BaseStorageService:
    """Return the configured storage backend (cached per app)."""
    if "storage" not in current_app.extensions:
        backend = current_app.config.get("STORAGE_BACKEND", "local").lower()

        if backend == "s3":
            service = S3StorageService(
                bucket=current_app.config["S3_BUCKET"],
                region=current_app.config.get("AWS_REGION", "us-east-1"),
            )
        elif backend == "supabase":
            service = SupabaseStorageService(
                url=current_app.config["SUPABASE_URL"],
                service_key=current_app.config["SUPABASE_SERVICE_KEY"],
                bucket=current_app.config.get("SUPABASE_BUCKET", "hobby-tracker"),
            )
        else:
            service = LocalStorageService(current_app.config["UPLOAD_FOLDER"])

        current_app.extensions["storage"] = service

    return current_app.extensions["storage"]