"""
Cloud Authentication Service
============================

Responsibilities:
  1. Hash passwords before storing them (never store plaintext).
  2. Verify a password against a stored hash.
  3. Issue signed JWTs after successful login.
  4. Decode/validate JWTs on protected requests.

Password hashing uses PBKDF2-SHA256 with a per-user random salt
(provided by Werkzeug). In production you would use bcrypt/argon2 —
the interface here stays identical.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash


class AuthError(Exception):
    """Raised for authentication failures (expired / invalid token)."""


# ---------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------
def hash_password(plain_password: str) -> str:
    """Return a salted PBKDF2-SHA256 hash. Safe to store in the database."""
    return generate_password_hash(plain_password, method="pbkdf2:sha256", salt_length=16)


def verify_password(password_hash: str, plain_password: str) -> bool:
    """Constant-time comparison of a candidate password against a stored hash."""
    try:
        return check_password_hash(password_hash, plain_password)
    except Exception:
        return False


# ---------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------
def create_access_token(user_id: str, extra_claims: Optional[dict] = None) -> str:
    """Create a signed JWT for the given user."""
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=current_app.config["JWT_EXPIRES_MINUTES"])

    payload = {
        "sub": str(user_id),      # subject = user id (PyJWT requires a string)
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "iss": "hobby-skills-tracker",
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def decode_access_token(token: str) -> dict:
    """
    Validate a JWT and return its payload.

    Raises AuthError for expired or tampered tokens — the middleware
    converts this into an HTTP 401 response.
    """
    try:
        return jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
            issuer="hobby-skills-tracker",
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token has expired. Please log in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Invalid authentication token.") from exc