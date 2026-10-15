"""SQL access layer for ``fridge_item_versions`` and ``fridge_item_audit``.

Both tables are written exclusively by the triggers declared in ``app/schema.sql``,
therefore this module is read-only: it exposes the history of a fridge item and
the audit trail of a user.
"""

from __future__ import annotations

from ..db import Database

VERSION_COLUMNS = (
    "id, fridge_items_id, version, product_name, expiration_date, quantity, updated_at"
)
AUDIT_COLUMNS = (
    "id, action_type, user_id, product_name, expiration_date, quantity, "
    "action_time, old_values, new_value"
)


def list_versions(db: Database, item_id: int | None = None) -> list[dict]:
    """Return item versions, oldest first (all items when ``item_id`` is omitted)."""
    if item_id is None:
        sql = f"SELECT {VERSION_COLUMNS} FROM fridge_item_versions ORDER BY id"
        return db.fetch_all(sql)
    sql = f"""
        SELECT {VERSION_COLUMNS}
        FROM fridge_item_versions
        WHERE fridge_items_id = %s
        ORDER BY version, id
    """
    return db.fetch_all(sql, (item_id,))


def list_audit(db: Database, *, user_id: int | None = None) -> list[dict]:
    """Return audit entries, oldest first (all users when ``user_id`` is omitted)."""
    if user_id is None:
        sql = f"SELECT {AUDIT_COLUMNS} FROM fridge_item_audit ORDER BY id"
        return db.fetch_all(sql)
    sql = f"""
        SELECT {AUDIT_COLUMNS}
        FROM fridge_item_audit
        WHERE user_id = %s
        ORDER BY id
    """
    return db.fetch_all(sql, (user_id,))
