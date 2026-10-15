"""SQL access layer for the ``fridge_items`` table (parameterised queries only).

The primary key is ``item_id`` (docs/db_scheme.png); the API keeps exposing it as
``id`` (see ``app.serializers``).
"""

from __future__ import annotations

from datetime import date
from typing import Sequence

from ..db import Database

FRIDGE_COLUMNS = "item_id, user_id, product_name, expiration_date, quantity, last_added"
INSERT_SQL = """
    INSERT INTO fridge_items (user_id, product_name, expiration_date, quantity)
    VALUES (%s, %s, %s, %s)
"""


def list_items(db: Database) -> list[dict]:
    """Return fridge items of all users (openapi.yaml: no filtering by token)."""
    sql = f"SELECT {FRIDGE_COLUMNS} FROM fridge_items ORDER BY expiration_date, item_id"
    return db.fetch_all(sql)


def list_user_items(db: Database, user_id: int) -> list[dict]:
    """Return fridge items of a single user."""
    sql = f"""
        SELECT {FRIDGE_COLUMNS}
        FROM fridge_items
        WHERE user_id = %s
        ORDER BY expiration_date, item_id
    """
    return db.fetch_all(sql, (user_id,))


def insert_items(db: Database, items: Sequence[dict]) -> int:
    """Insert many fridge items in a single transaction and return the row count."""
    params = [
        (item["user_id"], item["product_name"], item["expiration_date"], item["quantity"])
        for item in items
    ]
    return db.execute_many(INSERT_SQL, params)


def list_expired_items(
    db: Database, *, user_id: int | None = None, today: date | None = None
) -> list[dict]:
    """Return items expired before ``today`` (all users when ``user_id`` is omitted)."""
    reference = today or date.today()
    if user_id is None:
        sql = f"""
            SELECT {FRIDGE_COLUMNS}
            FROM fridge_items
            WHERE expiration_date < %s
            ORDER BY expiration_date, item_id
        """
        return db.fetch_all(sql, (reference,))
    sql = f"""
        SELECT {FRIDGE_COLUMNS}
        FROM fridge_items
        WHERE user_id = %s AND expiration_date < %s
        ORDER BY expiration_date, item_id
    """
    return db.fetch_all(sql, (user_id, reference))


def delete_expired_items(db: Database, *, user_id: int | None = None) -> int:
    """Delete expired items and return the number of removed rows."""
    if user_id is None:
        return db.execute("DELETE FROM fridge_items WHERE expiration_date < CURRENT_DATE")
    sql = "DELETE FROM fridge_items WHERE expiration_date < CURRENT_DATE AND user_id = %s"
    return db.execute(sql, (user_id,))


def list_user_ids_with_expired_items(db: Database) -> list[int]:
    """Return ids of users having at least one expired item (used by the worker)."""
    sql = """
        SELECT DISTINCT user_id
        FROM fridge_items
        WHERE expiration_date < CURRENT_DATE
        ORDER BY user_id
    """
    return [int(row["user_id"]) for row in db.fetch_all(sql)]
