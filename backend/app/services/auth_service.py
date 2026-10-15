"""Registration and authentication business logic."""

from __future__ import annotations

from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from ..db import Database
from ..errors import BadRequest, Unauthorized
from ..models import users as users_model
from ..security import create_access_token
from ..validation import MAX_SHORT_FIELD_LENGTH, MIN_PASSWORD_LENGTH, require_email, require_string

# A dummy hash keeps the response time of a failed login close to a successful one.
DUMMY_PASSWORD_HASH = generate_password_hash("timing-safety-placeholder-password")
ALLOWED_TERM_TYPES = (str, list, dict)


def _raw_terms(payload: dict, field: str) -> Any:
    """Return ``payload[field]`` unchanged (openapi.yaml: stored "as is")."""
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, ALLOWED_TERM_TYPES):
        raise BadRequest(f"Field '{field}' must be a string or an array of strings")
    return value


def register_user(db: Database, payload: dict) -> dict:
    """Create a user and return the ``/register`` response body."""
    username = require_string(payload, "username", max_length=MAX_SHORT_FIELD_LENGTH)
    email = require_email(payload)
    password = require_string(
        payload, "password", max_length=MAX_SHORT_FIELD_LENGTH, min_length=MIN_PASSWORD_LENGTH
    )
    user_id = users_model.create_user(
        db,
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        allergies=_raw_terms(payload, "allergies"),
        preferences=_raw_terms(payload, "preferences"),
    )
    return {"message": "User registered successfully", "user_id": user_id}


def authenticate(db: Database, payload: dict) -> str:
    """Validate credentials and return a JWT access token."""
    email = require_email(payload)
    password = require_string(payload, "password", max_length=MAX_SHORT_FIELD_LENGTH)

    user = users_model.get_user_by_email(db, email)
    password_hash = user["password_hash"] if user is not None else DUMMY_PASSWORD_HASH
    if not check_password_hash(password_hash, password) or user is None:
        raise Unauthorized("Invalid email or password")
    return create_access_token(int(user["id"]))
