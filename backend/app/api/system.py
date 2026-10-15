"""System endpoints: ``/``, ``/health`` and ``/ready``."""

from __future__ import annotations

from flask import Blueprint, Response, jsonify

from ..context import get_db

bp = Blueprint("system", __name__)

INDEX_GREETING = "Welcome to the recipe app!"


@bp.get("/")
def index() -> Response:
    """Return the greeting declared for ``GET /`` in openapi.yaml."""
    return Response(INDEX_GREETING, mimetype="text/plain")


@bp.get("/health")
def health() -> tuple:
    """Liveness probe: the process is up (no database access, CONTRIBUTION.md §8)."""
    return jsonify({"status": "ok"}), 200


@bp.get("/ready")
def ready() -> tuple:
    """Readiness probe: the database answers a trivial query."""
    if get_db().health_check():
        return jsonify({"status": "ready", "database": "ok"}), 200
    return jsonify({"status": "not_ready", "database": "unavailable"}), 503
