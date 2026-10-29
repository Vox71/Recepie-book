"""Favourite endpoints: ``/favorite_recipes`` and ``/favorite_recipes/{id}``.

All three routes are personal, so they are protected by ``token_required`` and take the
owner from the token only (CONTRIBUTION.md §3); the body of ``POST`` cannot choose a
user even if a ``user_id`` field is sent.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..context import get_db
from ..security import current_user_id, token_required
from ..services import favorites_service
from ..validation import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    MAX_PAGE_OFFSET,
    json_object_body,
    query_int,
)

bp = Blueprint("favorites", __name__)


@bp.get("/favorite_recipes")
@token_required
def list_favorites() -> tuple:
    """Return a page of the favourites of the token owner: ``?limit=&offset=``."""
    limit = query_int("limit", default=DEFAULT_PAGE_LIMIT, minimum=1, maximum=MAX_PAGE_LIMIT)
    offset = query_int("offset", default=0, minimum=0, maximum=MAX_PAGE_OFFSET)
    rows = favorites_service.list_favorites(get_db(), current_user_id(), limit=limit, offset=offset)
    return jsonify(rows), 200


@bp.post("/favorite_recipes")
@token_required
def add_favorite() -> tuple:
    """Add a recipe to the favourites of the token owner (idempotent)."""
    payload = json_object_body()
    return jsonify(favorites_service.add_favorite(get_db(), current_user_id(), payload)), 201


@bp.delete("/favorite_recipes/<int:recipe_id>")
@token_required
def remove_favorite(recipe_id: int) -> tuple:
    """Remove a recipe from the favourites of the token owner or return 404."""
    return (
        jsonify(favorites_service.remove_favorite(get_db(), current_user_id(), recipe_id)),
        200,
    )
