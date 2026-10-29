"""Favourite recipes: the personal list behind ``/favorite_recipes``.

Every function takes ``user_id`` from the token (CONTRIBUTION.md §3); the request body
and the URL never choose the owner, so one user cannot read or change the favourites
of another.
"""

from __future__ import annotations

from ..db import Database
from ..errors import NotFound
from ..models import favorites as favorites_model
from ..models import recipes as recipes_model
from ..serializers import serialize_recipe
from ..validation import require_positive_int


def list_favorites(db: Database, user_id: int, *, limit: int, offset: int) -> list[dict]:
    """Return one page of the favourites of the token owner, newest first."""
    rows = favorites_model.list_favorites_page(db, user_id, limit=limit, offset=offset)
    return [serialize_recipe(row) for row in rows]


def add_favorite(db: Database, user_id: int, payload: dict) -> dict:
    """Add a recipe to the favourites of the token owner.

    The pair ``(user_id, recipe_id)`` is unique (``favorite_recipes_user_recipe_key``),
    so a repeat is not an error: nothing is inserted and the message says so.
    """
    recipe_id = require_positive_int(payload, "recipe_id")
    if recipes_model.get_recipe(db, recipe_id) is None:
        raise NotFound(f"Recipe {recipe_id} not found")
    if favorites_model.add_favorite(db, user_id, recipe_id):
        return {"message": f"Recipe {recipe_id} added to favourites"}
    return {"message": f"Recipe {recipe_id} is already in favourites"}


def remove_favorite(db: Database, user_id: int, recipe_id: int) -> dict:
    """Remove a recipe from the favourites of the token owner or raise 404.

    A favourite of another user is not visible here, so it is reported as missing
    (404) instead of 403: the answer does not disclose whether the row exists.
    """
    if not favorites_model.remove_favorite(db, user_id, recipe_id):
        raise NotFound(f"Recipe {recipe_id} is not in the favourites of this user")
    return {"message": f"Recipe {recipe_id} removed from favourites"}
