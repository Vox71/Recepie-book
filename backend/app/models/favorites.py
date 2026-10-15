"""SQL access layer for the ``favorite_recipes`` table (parameterised queries only)."""

from __future__ import annotations

from ..db import Database
from ..models.recipes import RECIPE_COLUMNS

FAVORITE_COLUMNS = "id, user_id, recipe_id"


def add_favorite(db: Database, user_id: int, recipe_id: int) -> bool:
    """Mark a recipe as favourite; ``False`` when the pair already exists."""
    sql = """
        INSERT INTO favorite_recipes (user_id, recipe_id)
        VALUES (%s, %s)
        ON CONFLICT ON CONSTRAINT favorite_recipes_user_recipe_key DO NOTHING
        RETURNING id
    """
    return db.fetch_one(sql, (user_id, recipe_id)) is not None


def remove_favorite(db: Database, user_id: int, recipe_id: int) -> bool:
    """Remove a favourite; ``False`` when the pair was not stored."""
    sql = "DELETE FROM favorite_recipes WHERE user_id = %s AND recipe_id = %s"
    return db.execute(sql, (user_id, recipe_id)) > 0


def list_favorites(db: Database, user_id: int) -> list[dict]:
    """Return the favourite recipes of ``user_id`` as ``recipes`` rows."""
    sql = f"""
        SELECT {", ".join(f"r.{column.strip()}" for column in RECIPE_COLUMNS.split(","))}
        FROM favorite_recipes AS f
        JOIN recipes AS r ON r.id = f.recipe_id
        WHERE f.user_id = %s
        ORDER BY r.id
    """
    return db.fetch_all(sql, (user_id,))


def is_favorite(db: Database, user_id: int, recipe_id: int) -> bool:
    """True when the recipe is stored as a favourite of ``user_id``."""
    sql = "SELECT 1 AS found FROM favorite_recipes WHERE user_id = %s AND recipe_id = %s"
    return db.fetch_one(sql, (user_id, recipe_id)) is not None


def recipe_ids(db: Database, user_id: int) -> list[int]:
    """Return the ids of the favourite recipes of ``user_id``."""
    sql = "SELECT recipe_id FROM favorite_recipes WHERE user_id = %s ORDER BY recipe_id"
    return [int(row["recipe_id"]) for row in db.fetch_all(sql, (user_id,))]
