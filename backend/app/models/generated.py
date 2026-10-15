"""SQL access layer for the ``generated_recipes`` table (parameterised queries only).

``generated_recipes`` stores which recipes were offered to a user, so that the
history of ``/suggest_recipes`` and ``/recommend_recipes`` answers can be audited.
"""

from __future__ import annotations

from typing import Sequence

from ..db import Database

INSERT_SQL = """
    INSERT INTO generated_recipes (user_id, recipes_id)
    VALUES (%s, %s)
"""
GENERATED_COLUMNS = "id, user_id, recipes_id, generated_on"


def record_generated(db: Database, user_id: int, recipe_ids: Sequence[int]) -> int:
    """Store the recipes offered to ``user_id`` and return the number of rows."""
    if not recipe_ids:
        return 0
    params = [(user_id, recipe_id) for recipe_id in recipe_ids]
    return db.execute_many(INSERT_SQL, params)


def list_generated(db: Database, user_id: int, *, limit: int | None = None) -> list[dict]:
    """Return the generated rows of a user, newest first."""
    sql = f"""
        SELECT {GENERATED_COLUMNS}
        FROM generated_recipes
        WHERE user_id = %s
        ORDER BY generated_on DESC, id DESC
    """
    if limit is None:
        return db.fetch_all(sql, (user_id,))
    return db.fetch_all(f"{sql} LIMIT %s", (user_id, limit))


def list_recipes_for_user(db: Database, user_id: int, *, limit: int | None = None) -> list[dict]:
    """Return the recipes that were offered to ``user_id`` (joined with ``recipes``)."""
    sql = """
        SELECT r.id, r.recipe_name, r.ingredients, r.instruction, r.difficulty_level,
               g.generated_on
        FROM generated_recipes AS g
        JOIN recipes AS r ON r.id = g.recipes_id
        WHERE g.user_id = %s
        ORDER BY g.generated_on DESC, g.id DESC
    """
    if limit is None:
        return db.fetch_all(sql, (user_id,))
    return db.fetch_all(f"{sql} LIMIT %s", (user_id, limit))


def delete_generated(db: Database, user_id: int) -> int:
    """Drop the generated history of a user and return the number of removed rows."""
    return db.execute("DELETE FROM generated_recipes WHERE user_id = %s", (user_id,))
