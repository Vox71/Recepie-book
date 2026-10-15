"""Recipe CRUD business logic."""

from __future__ import annotations

from ..db import Database
from ..errors import NotFound
from ..models import recipes as recipes_model
from ..serializers import serialize_recipe
from ..validation import MAX_TEXT_FIELD_LENGTH, require_string


def _validated(payload: dict) -> dict:
    """Validate the ``RecipeInput`` schema declared in openapi.yaml."""
    return {
        "name": require_string(payload, "name"),
        "ingredients": require_string(payload, "ingredients", max_length=MAX_TEXT_FIELD_LENGTH),
        "instructions": require_string(payload, "instructions", max_length=MAX_TEXT_FIELD_LENGTH),
        "cuisine_type": require_string(payload, "cuisine_type"),
        "difficulty_level": require_string(payload, "difficulty_level"),
    }


def list_recipes(db: Database) -> list[dict]:
    """Return all recipes."""
    return [serialize_recipe(row) for row in recipes_model.list_recipes(db)]


def get_recipe(db: Database, recipe_id: int) -> dict:
    """Return one recipe or raise 404."""
    row = recipes_model.get_recipe(db, recipe_id)
    if row is None:
        raise NotFound(f"Recipe {recipe_id} not found")
    return serialize_recipe(row)


def create_recipe(db: Database, payload: dict) -> dict:
    """Create a recipe and return the ``/recipes`` POST response body."""
    recipe_id = recipes_model.create_recipe(db, _validated(payload))
    return {"message": f"Recipe {recipe_id} added successfully"}


def update_recipe(db: Database, recipe_id: int, payload: dict) -> dict:
    """Overwrite a recipe or raise 404."""
    if not recipes_model.update_recipe(db, recipe_id, _validated(payload)):
        raise NotFound(f"Recipe {recipe_id} not found")
    return {"message": f"Recipe {recipe_id} updated successfully"}


def delete_recipe(db: Database, recipe_id: int) -> dict:
    """Delete a recipe or raise 404."""
    if not recipes_model.delete_recipe(db, recipe_id):
        raise NotFound(f"Recipe {recipe_id} not found")
    return {"message": f"Recipe {recipe_id} deleted successfully"}
