"""Recipe endpoints: ``/recipes`` and ``/recipes/{id}``."""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..context import get_db
from ..services import recipe_service
from ..validation import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    MAX_PAGE_OFFSET,
    json_object_body,
    query_int,
)

bp = Blueprint("recipes", __name__)


@bp.get("/recipes")
def list_recipes() -> tuple:
    """Return a page of recipes: ``?limit=&offset=`` (CONTRIBUTION.md §4)."""
    limit = query_int("limit", default=DEFAULT_PAGE_LIMIT, minimum=1, maximum=MAX_PAGE_LIMIT)
    offset = query_int("offset", default=0, minimum=0, maximum=MAX_PAGE_OFFSET)
    return jsonify(recipe_service.list_recipes(get_db(), limit=limit, offset=offset)), 200


@bp.post("/recipes")
def create_recipe() -> tuple:
    """Create a recipe.

    openapi.yaml documents that the token check is commented out for this route,
    therefore no ``token_required`` decorator is applied (see CONTRIBUTION.md §16).
    """
    payload = json_object_body()
    return jsonify(recipe_service.create_recipe(get_db(), payload)), 201


@bp.get("/recipes/<int:recipe_id>")
def get_recipe(recipe_id: int) -> tuple:
    """Return a single recipe or 404."""
    return jsonify(recipe_service.get_recipe(get_db(), recipe_id)), 200


@bp.put("/recipes/<int:recipe_id>")
def update_recipe(recipe_id: int) -> tuple:
    """Overwrite a recipe or return 404."""
    payload = json_object_body()
    return jsonify(recipe_service.update_recipe(get_db(), recipe_id, payload)), 200


@bp.delete("/recipes/<int:recipe_id>")
def delete_recipe(recipe_id: int) -> tuple:
    """Delete a recipe or return 404."""
    return jsonify(recipe_service.delete_recipe(get_db(), recipe_id)), 200
