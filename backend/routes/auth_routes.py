"""
Authentication routes.

POST /api/register
POST /api/login
POST /api/logout
GET  /api/me
"""
from __future__ import annotations

from flask import Blueprint, g, request

from backend.middleware.auth_middleware import require_auth
from backend.utils.ids import new_id
from backend.utils.responses import created, error, ok
from backend.utils.validators import validate_registration
from cloud.auth_service import create_access_token, hash_password, verify_password
from cloud.database_service import execute, query_one
from analytics.progress_service import now_iso

auth_bp = Blueprint("auth", __name__, url_prefix="/api")


def _public_user(row: dict) -> dict:
    """Strip sensitive columns before sending a user object to the client."""
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


# ---------------------------------------------------------------------
@auth_bp.post("/register")
def register():
    """
    Create a new account.

    Request : {"name","username","email","password"}
    Response: 201 {"token": "...", "user": {...}}
    Errors  : 400 validation, 409 duplicate username/email
    """
    payload = request.get_json(silent=True) or {}

    errors = validate_registration(payload)
    if errors:
        return error("Validation failed.", 400, details=errors)

    name = payload["name"].strip()
    username = payload["username"].strip().lower()
    email = payload["email"].strip().lower()
    password = payload["password"]

    # Uniqueness checks (also enforced by UNIQUE constraints in the schema)
    if query_one("SELECT 1 AS x FROM users WHERE email = ?", (email,)):
        return error("An account with this email already exists.", 409)
    if query_one("SELECT 1 AS x FROM users WHERE username = ?", (username,)):
        return error("This username is already taken.", 409)

    user_id = new_id("user")
    execute(
        """
        INSERT INTO users (user_id, name, username, email, password_hash,
                           profile_picture, bio, interests, created_at)
        VALUES (?, ?, ?, ?, ?, NULL, '', '', ?)
        """,
        (user_id, name, username, email, hash_password(password), now_iso()),
    )

    user = query_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
    token = create_access_token(user_id)
    return created({"token": token, "user": _public_user(user)})


# ---------------------------------------------------------------------
@auth_bp.post("/login")
def login():
    """
    Authenticate and receive a JWT.

    Request : {"identifier": "email-or-username", "password": "..."}
              ("email" is also accepted as an alias for identifier)
    Response: 200 {"token": "...", "user": {...}}
    Errors  : 400 missing fields, 401 bad credentials
    """
    payload = request.get_json(silent=True) or {}
    identifier = (payload.get("identifier") or payload.get("email") or payload.get("username") or "").strip().lower()
    password = payload.get("password") or ""

    if not identifier or not password:
        return error("Both identifier and password are required.", 400)

    user = query_one(
        "SELECT * FROM users WHERE email = ? OR username = ?",
        (identifier, identifier),
    )

    # Same generic message for "no such user" and "wrong password"
    # so attackers cannot enumerate valid accounts.
    if not user or not verify_password(user["password_hash"], password):
        return error("Invalid credentials. Please check and try again.", 401)

    token = create_access_token(user["user_id"])
    return ok({"token": token, "user": _public_user(user)})


# ---------------------------------------------------------------------
@auth_bp.post("/logout")
@require_auth
def logout():
    """
    Log the user out.

    JWTs are stateless, so the server cannot "delete" a token. The client
    discards it. In a hardened system you would also add the token's `jti`
    to a Redis denylist until its natural expiry.
    """
    return ok({"message": "Logged out successfully. Please discard your token."})


# ---------------------------------------------------------------------
@auth_bp.get("/me")
@require_auth
def me():
    """Return the currently authenticated user."""
    user = query_one("SELECT * FROM users WHERE user_id = ?", (g.user_id,))
    if not user:
        return error("Account no longer exists.", 401)
    return ok({"user": _public_user(user)})