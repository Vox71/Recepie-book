"""Serialization helpers.

Rows coming from PostgreSQL carry ``date``/``datetime`` objects and the database
column names (``recipe_name``, ``instruction``, ``item_id``), while openapi.yaml
declares ISO 8601 strings and the API field names (``name``, ``instructions``, ``id``).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Sequence


def iso_date(value: date | None) -> str | None:
    """Serialize a ``date`` as ``YYYY-MM-DD``."""
    return value.isoformat() if value is not None else None


def iso_datetime(value: datetime | None) -> str | None:
    """Serialize a ``datetime`` in ISO 8601 (with offset when available)."""
    return value.isoformat() if value is not None else None


def as_int(value: Any) -> int | None:
    """Serialize an integer column value as a JSON integer."""
    return int(value) if value is not None else None


def serialize_recipe(row: dict, ingredient_list: Sequence[dict] | None = None) -> dict:
    """Map a ``recipes`` row onto ``components.schemas.Recipe``.

    ``ingredient_list`` is the normalized ``recipe_ingredients`` of this recipe (task 5);
    it stays an empty array for a recipe created through ``POST /recipes``, because the
    structured rows are written by the dataset importer only.  ``source_url``,
    ``instructions`` and ``difficulty_level`` are ``null`` for an imported recipe: the
    povarenok dataset has no instructions and no difficulty, and a manual recipe has no
    source.
    """
    return {
        "id": row["id"],
        "name": row["recipe_name"],
        "ingredients": row["ingredients"],
        "ingredient_list": list(ingredient_list or []),
        "instructions": row["instruction"],
        "difficulty_level": row["difficulty_level"],
        "source_url": row["source_url"],
    }


def serialize_fridge_item(row: dict) -> dict:
    """Map a ``fridge_items`` row onto ``components.schemas.FridgeItem``."""
    return {
        "id": row["item_id"],
        "user_id": row["user_id"],
        "product_name": row["product_name"],
        "expiration_date": iso_date(row["expiration_date"]),
        "quantity": as_int(row["quantity"]),
        "last_added": iso_datetime(row["last_added"]),
    }


def serialize_expired_product(row: dict) -> dict:
    """Map a ``fridge_items`` row onto the ``expired_products`` item schema."""
    return {
        "id": row["item_id"],
        "name": row["product_name"],
        "expiration_date": iso_date(row["expiration_date"]),
    }
