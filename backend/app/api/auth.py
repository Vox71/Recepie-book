"""Authentication endpoints: ``/register``, ``/login``, ``/protected``."""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..context import get_db
from ..security import current_user_id, rate_limit, token_required
from ..services import auth_service
from ..validation import json_object_body

bp = Blueprint("auth", __name__)


@bp.post("/register")
@rate_limit("register")
def register() -> tuple:
    """Register a user (``RegisterRequest`` in openapi.yaml)."""
    payload = json_object_body()
    return jsonify(auth_service.register_user(get_db(), payload)), 201


@bp.post("/login")
@rate_limit("login")
def login() -> tuple:
    """Authenticate a user and return a JWT access token (``LoginResponse``)."""
    payload = json_object_body()
    return jsonify({"token": auth_service.authenticate(get_db(), payload)}), 200


@bp.get("/protected")
@token_required
def protected() -> tuple:
    """Echo the id from the token; ``user_id`` is a string in openapi.yaml."""
    return jsonify({"message": "Access granted", "user_id": str(current_user_id())}), 200
