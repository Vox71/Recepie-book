"""SQL access layer for the ``recipes`` table (parameterised queries only)."""

from __future__ import annotations

from typing import Sequence

from ..db import Database

RECIPE_COLUMNS = "id, recipe_name, ingredients, instruction, difficulty_level"


def list_recipes(db: Database, *, limit: int, offset: int) -> list[dict]:
    """Return one page of recipes ordered by id."""
    sql = f"SELECT {RECIPE_COLUMNS} FROM recipes ORDER BY id LIMIT %s OFFSET %s"
    return db.fetch_all(sql, (limit, offset))


def list_all_recipes(db: Database) -> list[dict]:
    """Return every recipe ordered by id.

    The baseline scoring and the stub ML module compare the candidate with the whole
    catalogue; a trained index replaces this full scan in sprint 2 (task 6). The HTTP
    address is paginated and uses ``list_recipes`` instead.
    """
    return db.fetch_all(f"SELECT {RECIPE_COLUMNS} FROM recipes ORDER BY id")


def list_recipes_for_model(db: Database, *, limit: int | None = None) -> list[dict]:
    """Return ``id``/``recipe_name``/``ingredients`` of recipes for the v1 model (task 6.0).

    The trainer needs the id (to look up ``recipe_ingredients``), the ingredient text (the
    fallback for recipes created through ``POST /recipes``) and the name (only for the
    diagnostics of a run); the instruction is not read, so a 147 thousand row catalogue
    fits into memory.
    """
    sql = "SELECT id, recipe_name, ingredients FROM recipes ORDER BY id"
    params: tuple[int, ...] = ()
    if limit is not None:
        sql += " LIMIT %s"
        params = (limit,)
    return db.fetch_all(sql, params)


def create_recipe(db: Database, data: dict) -> int:
    """Insert a recipe and return the generated id."""
    sql = """
        INSERT INTO recipes (recipe_name, ingredients, instruction, difficulty_level)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """
    params = (
        data["name"],
        data["ingredients"],
        data["instructions"],
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
        SET recipe_name = %s, ingredients = %s, instruction = %s, difficulty_level = %s
        WHERE id = %s
    """
    params = (
        data["name"],
        data["ingredients"],
        data["instructions"],
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
        ORDER BY recipe_name
        LIMIT %s
    """
    return db.fetch_all(sql, (list(patterns), limit))


def list_ingredient_names(db: Database, recipe_ids: Sequence[int]) -> dict[int, list[str]]:
    """Return the normalized ingredient names of ``recipe_ids``, keyed by recipe id.

    ``recipe_ingredients`` (one row per ingredient, ordered by ``sort_order``) is written
    by the povarenok importer and is the source of truth for the allergen filter
    (sprint 2, task 6.1).  Recipes created through ``POST /recipes`` have no rows here,
    so the caller falls back to the ``recipes.ingredients`` text.
    """
    if not recipe_ids:
        return {}
    sql = """
        SELECT recipe_id, ingredient_name
        FROM recipe_ingredients
        WHERE recipe_id = ANY(%s)
        ORDER BY recipe_id, sort_order, id
    """
    names: dict[int, list[str]] = {}
    for row in db.fetch_all(sql, (list(recipe_ids),)):
        names.setdefault(int(row["recipe_id"]), []).append(str(row["ingredient_name"]))
    return names
