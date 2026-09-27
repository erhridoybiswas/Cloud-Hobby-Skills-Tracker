"""
Profile routes.

GET  /api/profile              (private — full profile)
PUT  /api/profile              (private — update)
GET  /api/users/<username>     (public  — safe subset + stats)
"""
from __future__ import annotations

from flask import Blueprint, g, request

from backend.middleware.auth_middleware import require_auth
from backend.utils.responses import error, not_found, ok
from backend.utils.validators import MAX_BIO_LENGTH, clean_text
from cloud.database_service import execute, query_one, query_scalar

profile_bp = Blueprint("profile", __name__, url_prefix="/api")


def _private_user(row: dict) -> dict:
    return {
        "user_id": row["user_id"],
        "name": row["name"],
        "username": row["username"],
        "email": row["email"],
        "profile_picture": row.get("profile_picture"),
        "bio": row.get("bio", ""),
        "interests": row.get("interests", ""),
        "created_at": row.get("created_at"),
    }


def _public_user(row: dict) -> dict:
    """Public profile — NOTE: email is deliberately excluded."""
    return {
        "user_id": row["user_id"],
        "name": row["name"],
        "username": row["username"],
        "profile_picture": row.get("profile_picture"),
        "bio": row.get("bio", ""),
        "interests": row.get("interests", ""),
        "created_at": row.get("created_at"),
    }


# ---------------------------------------------------------------------
@profile_bp.get("/profile")
@require_auth
def get_own_profile():
    user = query_one("SELECT * FROM users WHERE user_id = ?", (g.user_id,))
    if not user:
        return not_found("User")
    return ok({"user": _private_user(user)})


# ---------------------------------------------------------------------
@profile_bp.put("/profile")
@require_auth
def update_own_profile():
    """
    Update the authenticated user's profile.

    Only whitelisted fields are ever written — a client cannot escalate
    privileges by sending `is_admin: true`.
    """
    payload = request.get_json(silent=True) or {}
    errors: dict[str, str] = {}
    updates: dict = {}

    if "name" in payload:
        name, err = clean_text(payload.get("name"), 80, "Name")
        if err or not name:
            errors["name"] = err or "Name cannot be empty."
        else:
            updates["name"] = name

    if "bio" in payload:
        bio, err = clean_text(payload.get("bio"), MAX_BIO_LENGTH, "Bio")
        if err:
            errors["bio"] = err
        else:
            updates["bio"] = bio

    if "interests" in payload:
        interests, err = clean_text(payload.get("interests"), 300, "Interests")
        if err:
            errors["interests"] = err
        else:
            updates["interests"] = interests

    if "profile_picture" in payload:
        # This is a storage KEY returned by /api/files/upload, not raw bytes.
        picture, err = clean_text(payload.get("profile_picture"), 300, "Profile picture")
        if err:
            errors["profile_picture"] = err
        else:
            updates["profile_picture"] = picture

    if errors:
        return error("Validation failed.", 400, details=errors)
    if not updates:
        return error("No updatable fields were provided.", 400)

    set_clause = ", ".join(f"{column} = ?" for column in updates)
    execute(
        f"UPDATE users SET {set_clause} WHERE user_id = ?",
        (*updates.values(), g.user_id),
    )

    user = query_one("SELECT * FROM users WHERE user_id = ?", (g.user_id,))
    return ok({"user": _private_user(user)})


# ---------------------------------------------------------------------
@profile_bp.get("/users/<username>")
def get_public_profile(username: str):
    """Public profile with aggregate stats. No authentication required."""
    user = query_one("SELECT * FROM users WHERE username = ?", (username.strip().lower(),))
    if not user:
        return not_found("User")

    user_id = user["user_id"]
    stats = {
        "skills": query_scalar("SELECT COUNT(*) FROM skills WHERE user_id = ?", (user_id,)),
        "posts": query_scalar("SELECT COUNT(*) FROM posts WHERE user_id = ?", (user_id,)),
        "followers": query_scalar("SELECT COUNT(*) FROM follows WHERE following_id = ?", (user_id,)),
        "following": query_scalar("SELECT COUNT(*) FROM follows WHERE follower_id = ?", (user_id,)),
        "total_practice_minutes": query_scalar(
            "SELECT COALESCE(SUM(duration_minutes), 0) FROM practice_sessions WHERE user_id = ?",
            (user_id,),
        ),
    }

    return ok({"user": _public_user(user), "stats": stats})