"""
Authentication / Authorization middleware.

`@require_auth`  -> the endpoint returns 401 unless a valid Bearer token
                    is supplied. On success, `g.user_id` is set.

`@optional_auth` -> the endpoint works for anonymous users too, but if a
                    token IS supplied it is validated and `g.user_id` is set.
                    Used by the public feed so we can show "liked_by_me".

Authorization (i.e. "can THIS user touch THIS row?") is enforced in the
route handlers by always including `AND user_id = ?` in UPDATE/DELETE
statements — never by trusting an ID sent from the client.
"""
from __future__ import annotations

from functools import wraps

from flask import g, jsonify, request

from cloud.auth_service import AuthError, decode_access_token


def _extract_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[7:].strip()
    return token or None


def require_auth(view):
    """Reject the request with 401 unless a valid JWT is present."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Authentication required. Provide a Bearer token."}), 401
        try:
            payload = decode_access_token(token)
        except AuthError as exc:
            return jsonify({"error": str(exc)}), 401

        g.user_id = payload["sub"]
        g.token_payload = payload
        return view(*args, **kwargs)

    return wrapper


def optional_auth(view):
    """Attach `g.user_id` when a valid token is present; never reject."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        g.user_id = None
        token = _extract_token()
        if token:
            try:
                payload = decode_access_token(token)
                g.user_id = payload["sub"]
            except AuthError:
                g.user_id = None  # expired/invalid token is simply ignored here
        return view(*args, **kwargs)

    return wrapper