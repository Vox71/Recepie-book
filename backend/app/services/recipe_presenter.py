"""Presentation of recipe rows for the API (sprint 2, task 5).

Every address that answers with a recipe - ``GET /recipes``, ``GET /recipes/{id}``,
``GET /favorite_recipes``, ``GET /suggest_recipes`` and both modes of
``GET /recommend_recipes`` - must return the same object.  The flat ``ingredients`` text
comes from the ``recipes`` row, while ``ingredient_list`` lives in
``recipe_ingredients``, so the list of a page costs exactly one extra query here instead
of one per recipe (``docs/sprint-2-plan.md``, decision on the size of the answer).
"""

from __future__ import annotations

from typing import Sequence

from ..db import Database
from ..models import recipes as recipes_model
from ..serializers import serialize_recipe


def present_recipe(db: Database, row: dict) -> dict:
    """Serialize one recipe row with its normalized ingredient list."""
    return present_recipes(db, [row])[0]


def present_recipes(db: Database, rows: Sequence[dict]) -> list[dict]:
    """Serialize recipe rows, adding the ``recipe_ingredients`` of every recipe."""
    if not rows:
        return []
    details = recipes_model.list_ingredient_details(db, [int(row["id"]) for row in rows])
    return [serialize_recipe(row, details.get(int(row["id"]), [])) for row in rows]
