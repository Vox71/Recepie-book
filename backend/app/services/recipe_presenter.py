"""Presentation of recipe rows for the API (sprint 2, task 5; sprint 3, task 2).

Every address that answers with a recipe - ``GET /recipes``, ``GET /recipes/{id}``,
``GET /favorite_recipes``, ``GET /suggest_recipes`` and both modes of
``GET /recommend_recipes`` - must return the same object.  The flat ``ingredients`` text
comes from the ``recipes`` row, while ``ingredient_list`` lives in
``recipe_ingredients``, ``steps`` in ``recipe_steps`` and ``nutrition`` in
``recipe_nutrition``, so the list of a page costs exactly three extra queries here instead
of three per recipe (``docs/sprint-2-plan.md``, decision on the size of the answer).
"""

from __future__ import annotations

from typing import Sequence

from ..db import Database
from ..models import recipes as recipes_model
from ..serializers import serialize_recipe


def present_recipe(db: Database, row: dict) -> dict:
    """Serialize one recipe row with its ingredients, steps and nutrition."""
    return present_recipes(db, [row])[0]


def present_recipes(db: Database, rows: Sequence[dict]) -> list[dict]:
    """Serialize recipe rows, adding the child rows of every recipe in one query each."""
    if not rows:
        return []
    recipe_ids = [int(row["id"]) for row in rows]
    ingredients = recipes_model.list_ingredient_details(db, recipe_ids)
    steps = recipes_model.list_steps(db, recipe_ids)
    nutrition = recipes_model.list_nutrition(db, recipe_ids)
    return [
        serialize_recipe(
            row,
            ingredients.get(int(row["id"]), []),
            steps.get(int(row["id"]), []),
            nutrition.get(int(row["id"])),
        )
        for row in rows
    ]
