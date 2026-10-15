"""HTTP error types and error handlers.

Error payloads follow ``openapi.yaml`` (``components.schemas.Error``): a single
string field, e.g. ``{"error": "Recipe 42 not found"}``.  CONTRIBUTION.md §4 asks
for an object with ``code``/``message`` instead, so the contract of the published
API wins here.
"""

from __future__ import annotations

import logging

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Base class for errors that are safe to expose to API clients."""

    status_code = 400
    default_message = "Bad request"

    def __init__(self, message: str | None = None, status_code: int | None = None) -> None:
        self.message = message or self.default_message
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class BadRequest(ApiError):
    """400 — malformed or invalid input."""

    status_code = 400
    default_message = "Bad request"


class Unauthorized(ApiError):
    """401 — missing, invalid or expired token, or wrong credentials."""

    status_code = 401
    default_message = "Unauthorized"


class NotFound(ApiError):
    """404 — the requested resource does not exist."""

    status_code = 404
    default_message = "Not found"


class TooManyRequests(ApiError):
    """429 — request rate limit exceeded (CONTRIBUTION.md §3)."""

    status_code = 429
    default_message = "Too many requests"


class DatabaseUnavailable(ApiError):
    """503 — the database cannot serve the request."""

    status_code = 503
    default_message = "Database is unavailable"


def error_response(message: str, status_code: int):
    """Build a JSON error response in the format declared by openapi.yaml."""
    return jsonify({"error": message}), status_code


def register_error_handlers(app: Flask) -> None:
    """Attach handlers so that clients never see a traceback (CONTRIBUTION.md §7)."""

    @app.errorhandler(ApiError)
    def _handle_api_error(exc: ApiError):
        if exc.status_code >= 500:
            logger.error("Request failed: %s", exc.message)
        else:
            logger.info("Request rejected with %s: %s", exc.status_code, exc.message)
        return error_response(exc.message, exc.status_code)

    @app.errorhandler(HTTPException)
    def _handle_http_exception(exc: HTTPException):
        return error_response(exc.description or exc.name, exc.code or 500)

    @app.errorhandler(Exception)
    def _handle_unexpected_error(exc: Exception):
        logger.exception("Unhandled error: %s", type(exc).__name__)
        return error_response("Internal server error", 500)
