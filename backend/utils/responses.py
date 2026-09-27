"""
Standard JSON response helpers.

Every endpoint returns one of these shapes, so the frontend can always
rely on `error` being present when something went wrong.
"""
from __future__ import annotations

from typing import Any, Optional

from flask import jsonify


def ok(data: Optional[dict] = None, status: int = 200, **extra):
    """Success response: 200 by default."""
    payload: dict[str, Any] = {}
    if data:
        payload.update(data)
    payload.update(extra)
    return jsonify(payload), status


def created(data: Optional[dict] = None, **extra):
    """201 Created — used after POST that creates a resource."""
    return ok(data, status=201, **extra)


def error(message: str, status: int = 400, details: Optional[dict] = None):
    """Error response. `details` carries field-level validation messages."""
    payload: dict[str, Any] = {"error": message}
    if details:
        payload["details"] = details
    return jsonify(payload), status


def not_found(resource: str = "Resource"):
    return error(f"{resource} not found.", 404)


def forbidden(message: str = "You are not allowed to perform this action."):
    return error(message, 403)


def unauthorized(message: str = "Authentication required."):
    return error(message, 401)