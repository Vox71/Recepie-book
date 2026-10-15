"""Registration and authentication business logic."""

from __future__ import annotations

from werkzeug.security import check_password_hash, generate_password_hash

from ..db import Database
from ..errors import BadRequest, Unauthorized
from ..models import users as users_model
from ..security import create_access_token
from ..validation import (
    MAX_SHORT_FIELD_LENGTH,
    MAX_USERNAME_LENGTH,
    MIN_PASSWORD_LENGTH,
    join_terms,
    parse_terms,
    require_email,
    require_list_of_terms,
    require_string,
)

# A dummy hash keeps the response time of a failed login close to a successful one.
DUMMY_PASSWORD_HASH = generate_password_hash("timing-safety-placeholder-password")
ALLOWED_TERM_TYPES = (str, list, dict)


def _terms(payload: dict, field: str) -> list[str]:
    """Return ``allergies``/``preferences`` of ``/register`` as normalized terms.

    openapi.yaml accepts a string, an array or an object here, while the database
    stores comma separated text in ``users`` and one row per term in
    ``user_allergy_preferences`` (docs/db_scheme.png), so the value is normalized.
    """
    value = payload.get(field)
    if value is None:
        return []
    if not isinstance(value, ALLOWED_TERM_TYPES):
        raise BadRequest(f"Field '{field}' must be a string or an array of strings")
    return require_list_of_terms({field: parse_terms(value)}, field, required=False)


def register_user(db: Database, payload: dict) -> dict:
    """Create a user and return the ``/register`` response body."""
    username = require_string(payload, "username", max_length=MAX_USERNAME_LENGTH)
    email = require_email(payload)
    password = require_string(
        payload, "password", max_length=MAX_SHORT_FIELD_LENGTH, min_length=MIN_PASSWORD_LENGTH
    )
    allergies = _terms(payload, "allergies")
    preferences = _terms(payload, "preferences")
    user_id = users_model.create_user(
        db,
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        allergies=join_terms(allergies),
        preferences=join_terms(preferences),
        allergy_terms=allergies,
    )
    return {"message": "User registered successfully", "user_id": user_id}


def authenticate(db: Database, payload: dict) -> str:
    """Validate credentials and return a JWT access token."""
    email = require_email(payload)
    password = require_string(payload, "password", max_length=MAX_SHORT_FIELD_LENGTH)

    user = users_model.get_user_by_email(db, email)
    password_hash = user["password"] if user is not None else DUMMY_PASSWORD_HASH
    if not check_password_hash(password_hash, password) or user is None:
        raise Unauthorized("Invalid email or password")
    return create_access_token(int(user["id"]))
