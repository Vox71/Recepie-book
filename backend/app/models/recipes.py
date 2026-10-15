"""SQL access layer for the ``recipes`` table (parameterised queries only)."""

from __future__ import annotations

from typing import Sequence

from ..db import Database

RECIPE_COLUMNS = "id, name, ingredients, instructions, cuisine_type, difficulty_level"


def list_recipes(db: Database) -> list[dict]:
    """Return every recipe ordered by id."""
    return db.fetch_all(f"SELECT {RECIPE_COLUMNS} FROM recipes ORDER BY id")


def create_recipe(db: Database, data: dict) -> int:
    """Insert a recipe and return the generated id."""
    sql = """
        INSERT INTO recipes (name, ingredients, instructions, cuisine_type, difficulty_level)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """
    params = (
        data["name"],
        data["ingredients"],
        data["instructions"],
        data["cuisine_type"],
        data["difficulty_level"],
    )
    row = db.fetch_one(sql, params)
    return int(row["id"])


def get_recipe(db: Database, recipe_id: int) -> dict | None:
    """Return a single recipe or ``None``."""
    sql = f"SELECT {RECIPE_COLUMNS} FROM recipes WHERE id = %s"
    return db.fetch_one(sql, (recipe_id,))


def update_recipe(db: Database, recipe_id: int, data: dict) -> bool:
    """Overwrite a recipe; ``False`` when the recipe does not exist."""
    sql = """
        UPDATE recipes
        SET name = %s, ingredients = %s, instructions = %s, cuisine_type = %s, difficulty_level = %s
        WHERE id = %s
    """
    params = (
        data["name"],
        data["ingredients"],
        data["instructions"],
        data["cuisine_type"],
        data["difficulty_level"],
        recipe_id,
    )
    return db.execute(sql, params) > 0


def delete_recipe(db: Database, recipe_id: int) -> bool:
    """Delete a recipe; ``False`` when the recipe does not exist."""
    return db.execute("DELETE FROM recipes WHERE id = %s", (recipe_id,)) > 0


def find_recipes_with_ingredients(
    db: Database, patterns: Sequence[str], *, limit: int
) -> list[dict]:
    """Return recipes whose ``ingredients`` match any of the ``ILIKE`` patterns."""
    sql = f"""
        SELECT {RECIPE_COLUMNS}
        FROM recipes
        WHERE ingredients ILIKE ANY(%s)
        ORDER BY name
        LIMIT %s
    """
    return db.fetch_all(sql, (list(patterns), limit))
