"""SQL access layer for the ``users`` table (parameterised queries only).

``password`` stores the password *hash* (see ``app.security``), while ``allergies``
and ``preferences`` store comma separated terms: the text form of the rows that
``user_allergy_preferences`` keeps normalized (docs/db_scheme.png).
"""

from __future__ import annotations

from typing import Any, Sequence

from psycopg2 import errors as pg_errors

from ..db import Database
from ..errors import BadRequest

USER_COLUMNS = "id, username, email, password, allergies, preferences"
USERNAME_CONSTRAINT = "users_username_key"
EMAIL_CONSTRAINTS = frozenset({"users_email_key", "users_email_lower_key"})


def _duplicate_message(exc: pg_errors.UniqueViolation) -> str:
    """Turn a unique violation into a client friendly message."""
    constraint = getattr(exc.diag, "constraint_name", "") or ""
    if constraint in EMAIL_CONSTRAINTS:
        return "User with this email already exists"
    if constraint == USERNAME_CONSTRAINT:
        return "User with this username already exists"
    return "User already exists"


def _replace_allergy_preferences(cur: Any, user_id: int, terms: Sequence[str]) -> None:
    """Replace the normalized allergy rows of a user inside the current transaction."""
    cur.execute("DELETE FROM user_allergy_preferences WHERE user_id = %s", (user_id,))
    if terms:
        cur.executemany(
            "INSERT INTO user_allergy_preferences (user_id, allergy_name) VALUES (%s, %s)",
            [(user_id, term) for term in terms],
        )


def create_user(
    db: Database,
    *,
    username: str,
    email: str,
    password_hash: str,
    allergies: str | None = None,
    preferences: str | None = None,
    allergy_terms: Sequence[str] = (),
) -> int:
    """Insert a user with its allergies and return the generated id.

    Raises ``BadRequest`` when the e-mail or the username is already taken.
    """
    sql = """
        INSERT INTO users (username, email, password, allergies, preferences)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """
    params = (username, email, password_hash, allergies, preferences)
    try:
        with db.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            user_id = int(row["id"])
            _replace_allergy_preferences(cur, user_id, allergy_terms)
    except pg_errors.UniqueViolation as exc:
        raise BadRequest(_duplicate_message(exc)) from exc
    return user_id


def get_user_by_email(db: Database, email: str) -> dict | None:
    """Return the user with the given e-mail (case-insensitive) or ``None``."""
    sql = f"SELECT {USER_COLUMNS} FROM users WHERE lower(email) = lower(%s)"
    return db.fetch_one(sql, (email,))


def get_user_by_id(db: Database, user_id: int) -> dict | None:
    """Return the user with the given id or ``None``."""
    sql = f"SELECT {USER_COLUMNS} FROM users WHERE id = %s"
    return db.fetch_one(sql, (user_id,))


def replace_user_profile(
    db: Database,
    user_id: int,
    *,
    allergies: str | None,
    preferences: str | None,
    allergy_terms: Sequence[str],
) -> bool:
    """Replace the profile of a user in a single transaction.

    ``users`` keeps the text form of the terms and ``user_allergy_preferences``
    keeps the normalized allergy list, therefore both tables are written together.
    ``False`` means that the user does not exist and nothing was written.
    """
    with db.cursor() as cur:
        cur.execute(
            "UPDATE users SET allergies = %s, preferences = %s WHERE id = %s",
            (allergies, preferences, user_id),
        )
        if cur.rowcount == 0:
            return False
        _replace_allergy_preferences(cur, user_id, allergy_terms)
    return True


def list_user_allergies(db: Database, user_id: int) -> list[str]:
    """Return the normalized allergies of a user (an empty list when there are none)."""
    sql = "SELECT allergy_name FROM user_allergy_preferences WHERE user_id = %s ORDER BY id"
    return [str(row["allergy_name"]) for row in db.fetch_all(sql, (user_id,))]


def existing_ids(db: Database, user_ids: Sequence[int]) -> set[int]:
    """Return the subset of ``user_ids`` that exists in the ``users`` table."""
    if not user_ids:
        return set()
    rows = db.fetch_all("SELECT id FROM users WHERE id = ANY(%s)", (list(user_ids),))
    return {int(row["id"]) for row in rows}
