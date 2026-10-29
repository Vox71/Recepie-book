"""Allergen filtering of recipes (sprint 2, task 6.1).

The service is the bridge between the SQL layer and the dictionary of
``app.ml.allergens``: it loads the normalized ingredient lists of the recipes it is
given and drops the ones that contain a product the user is allergic to.

Ingredients come from ``recipe_ingredients`` (one row per ingredient, written by the
povarenok importer), because the flattened ``recipes.ingredients`` text cannot tell
"кокосовое молоко" from "молоко" reliably.  A recipe without rows - any recipe created
through ``POST /recipes`` - falls back to that text, so the filter never silently
passes an unchecked recipe.
"""

from __future__ import annotations

import logging
from typing import Sequence

from ..db import Database
from ..ml import allergens
from ..models import recipes as recipes_model

logger = logging.getLogger(__name__)


def filter_safe_recipes(
    db: Database, recipes: Sequence[dict], allergies: Sequence[str]
) -> tuple[list[dict], int]:
    """Return ``(safe_recipes, rejected_count)`` for the allergy profile of a user.

    An empty profile keeps every recipe: there is nothing to check against.
    """
    query = allergens.resolve_allergies(allergies)
    if not query:
        return list(recipes), 0

    recipe_ids = [int(row["id"]) for row in recipes if row.get("id") is not None]
    names_by_recipe = recipes_model.list_ingredient_names(db, recipe_ids)
    safe: list[dict] = []
    rejected = 0
    for row in recipes:
        matched = allergens.matched_allergens(ingredient_names(row, names_by_recipe), query)
        if matched:
            rejected += 1
            logger.info("Recipe %s rejected: allergen(s) %s", row.get("id"), ", ".join(matched))
            continue
        safe.append(row)
    return safe, rejected


def ingredient_names(row: dict, names_by_recipe: dict[int, list[str]] | None = None) -> list[str]:
    """Ingredient names of one recipe: the normalized rows, or the text as a fallback."""
    row_id = row.get("id")
    if row_id is not None:
        names = (names_by_recipe or {}).get(int(row_id))
        if names:
            return names
    return [row.get("ingredients") or ""]
