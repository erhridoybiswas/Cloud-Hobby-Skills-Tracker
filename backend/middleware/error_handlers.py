"""
Global error handlers.

Without these, an unhandled exception returns an HTML traceback which
breaks `fetch().json()` on the frontend and leaks internal details.
"""
from __future__ import annotations

import logging

from flask import current_app
from werkzeug.exceptions import HTTPException

from backend.utils.responses import error
from cloud.storage_service import StorageError

logger = logging.getLogger("hobby_tracker")


def register_error_handlers(app) -> None:
    """Attach handlers to the Flask app."""

    @app.errorhandler(400)
    def bad_request(exc):
        return error("Bad request. Check the request body.", 400)

    @app.errorhandler(401)
    def unauthorized(exc):
        return error("Authentication required.", 401)

    @app.errorhandler(403)
    def forbidden(exc):
        return error("You are not allowed to perform this action.", 403)

    @app.errorhandler(404)
    def not_found(exc):
        return error("The requested resource was not found.", 404)

    @app.errorhandler(405)
    def method_not_allowed(exc):
        return error("HTTP method not allowed for this endpoint.", 405)

    @app.errorhandler(413)
    def payload_too_large(exc):
        limit_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return error(f"Uploaded file is too large. Maximum size is {limit_mb} MB.", 413)

    @app.errorhandler(StorageError)
    def storage_failure(exc):
        logger.error("Object storage failure: %s", exc)
        return error("File storage is temporarily unavailable. Please retry.", 503)

    @app.errorhandler(HTTPException)
    def http_exception(exc: HTTPException):
        return error(exc.description or "Request failed.", exc.code or 500)

    @app.errorhandler(Exception)
    def unhandled(exc: Exception):
        logger.exception("Unhandled server error: %s", exc)
        # Never leak a stack trace to the client
        if current_app.config.get("TESTING"):
            raise exc
        return error("An internal server error occurred. Our team has been notified.", 500)

    @app.errorhandler(500)
    def internal_error(exc):
        return error("An internal server error occurred.", 500)