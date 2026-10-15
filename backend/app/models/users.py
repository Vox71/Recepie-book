"""SQL access layer for the ``users`` table (parameterised queries only)."""

from __future__ import annotations

from typing import Any, Sequence

from psycopg2 import errors as pg_errors
from psycopg2.extras import Json

from ..db import Database
from ..errors import BadRequest

USER_COLUMNS = "id, username, email, password_hash, allergies, preferences, created_at"
EMAIL_CONSTRAINT = "users_email_lower_key"
USERNAME_CONSTRAINT = "users_username_key"


def _as_json(value: Any) -> Json:
    """Adapt a Python value for a ``jsonb`` column (``[]`` when the value is missing)."""
    return Json([] if value is None else value)


def _duplicate_message(exc: pg_errors.UniqueViolation) -> str:
    """Turn a unique violation into a client friendly message."""
    constraint = getattr(exc.diag, "constraint_name", "") or ""
    if constraint == EMAIL_CONSTRAINT:
        return "User with this email already exists"
    if constraint == USERNAME_CONSTRAINT:
        return "User with this username already exists"
    return "User already exists"


def create_user(
    db: Database,
    *,
    username: str,
    email: str,
    password_hash: str,
    allergies: Any = None,
    preferences: Any = None,
) -> int:
    """Insert a user and return the generated id (400 when the user already exists)."""
    sql = """
        INSERT INTO users (username, email, password_hash, allergies, preferences)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """
    params = (username, email, password_hash, _as_json(allergies), _as_json(preferences))
    try:
        row = db.fetch_one(sql, params)
    except pg_errors.UniqueViolation as exc:
        raise BadRequest(_duplicate_message(exc)) from exc
    return int(row["id"])


def get_user_by_email(db: Database, email: str) -> dict | None:
    """Return the user with the given e-mail (case-insensitive) or ``None``."""
    sql = f"SELECT {USER_COLUMNS} FROM users WHERE lower(email) = lower(%s)"
    return db.fetch_one(sql, (email,))


def get_user_by_id(db: Database, user_id: int) -> dict | None:
    """Return the user with the given id or ``None``."""
    sql = f"SELECT {USER_COLUMNS} FROM users WHERE id = %s"
    return db.fetch_one(sql, (user_id,))


def update_user_terms(
    db: Database, user_id: int, *, allergies: list[str], preferences: list[str]
) -> bool:
    """Replace allergies and preferences of a user; ``False`` when the user is unknown."""
    sql = "UPDATE users SET allergies = %s, preferences = %s WHERE id = %s"
    affected = db.execute(sql, (Json(allergies), Json(preferences), user_id))
    return affected > 0


def existing_ids(db: Database, user_ids: Sequence[int]) -> set[int]:
    """Return the subset of ``user_ids`` that exists in the ``users`` table."""
    if not user_ids:
        return set()
    rows = db.fetch_all("SELECT id FROM users WHERE id = ANY(%s)", (list(user_ids),))
    return {int(row["id"]) for row in rows}
