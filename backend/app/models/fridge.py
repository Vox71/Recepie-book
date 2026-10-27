"""SQL access layer for the ``fridge_items`` table (parameterised queries only).

The primary key is ``item_id`` (docs/db_scheme.png); the API keeps exposing it as
``id`` (see ``app.serializers``).
"""

from __future__ import annotations

from typing import Sequence

from ..db import Database

FRIDGE_COLUMNS = "item_id, user_id, product_name, expiration_date, quantity, last_added"

# One definition of "expired" for every query below: the expiry date is already before
# today, so a product that expires today is still usable (openapi.yaml) and the
# comparison is strict. The date comes from PostgreSQL (CURRENT_DATE) rather than from
# Python: the web process and the database may run in different time zones, and a
# date.today() in one query next to CURRENT_DATE in another made /notify_expired and
# DELETE /delete_expired_products disagree around midnight.
EXPIRED_CONDITION = "expiration_date < CURRENT_DATE"

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


def list_expired_items(db: Database, *, user_id: int | None = None) -> list[dict]:
    """Return expired items (all users when ``user_id`` is omitted)."""
    if user_id is None:
        sql = f"""
            SELECT {FRIDGE_COLUMNS}
            FROM fridge_items
            WHERE {EXPIRED_CONDITION}
            ORDER BY expiration_date, item_id
        """
        return db.fetch_all(sql)
    sql = f"""
        SELECT {FRIDGE_COLUMNS}
        FROM fridge_items
        WHERE user_id = %s AND {EXPIRED_CONDITION}
        ORDER BY expiration_date, item_id
    """
    return db.fetch_all(sql, (user_id,))


def delete_expired_items(db: Database, *, user_id: int | None = None) -> int:
    """Delete expired items and return the number of removed rows."""
    if user_id is None:
        return db.execute(f"DELETE FROM fridge_items WHERE {EXPIRED_CONDITION}")
    sql = f"DELETE FROM fridge_items WHERE {EXPIRED_CONDITION} AND user_id = %s"
    return db.execute(sql, (user_id,))


def list_user_ids_with_expired_items(db: Database) -> list[int]:
    """Return ids of users having at least one expired item (used by the worker)."""
    sql = f"""
        SELECT DISTINCT user_id
        FROM fridge_items
        WHERE {EXPIRED_CONDITION}
        ORDER BY user_id
    """
    return [int(row["user_id"]) for row in db.fetch_all(sql)]
