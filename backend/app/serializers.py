"""Serialization helpers.

Rows coming from PostgreSQL carry ``date``/``datetime`` objects and the database
column names (``recipe_name``, ``instruction``, ``item_id``), while openapi.yaml
declares ISO 8601 strings and the API field names (``name``, ``instructions``, ``id``).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Sequence


def iso_date(value: date | None) -> str | None:
    """Serialize a ``date`` as ``YYYY-MM-DD``."""
    return value.isoformat() if value is not None else None


def iso_datetime(value: datetime | None) -> str | None:
    """Serialize a ``datetime`` in ISO 8601, always with an offset.

    ``openapi.yaml`` declares ``format: date-time``, which is RFC 3339 and therefore
    requires the offset.  ``fridge_items.last_added`` is a ``timestamp`` (without time
    zone) filled by ``current_timestamp``, so a naive value is taken as UTC instead of
    being sent without a zone - otherwise a strict client validator rejects the answer.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def as_int(value: Any) -> int | None:
    """Serialize an integer column value as a JSON integer."""
    return int(value) if value is not None else None


def as_float(value: Any) -> float | None:
    """Serialize a ``numeric`` column (``Decimal`` in psycopg2) as a JSON number."""
    return float(value) if value is not None else None


def serialize_recipe(
    row: dict,
    ingredient_list: Sequence[dict] | None = None,
    steps: Sequence[dict] | None = None,
    nutrition: dict | None = None,
) -> dict:
    """Map a ``recipes`` row onto ``components.schemas.Recipe``.

    ``ingredient_list`` is the normalized ``recipe_ingredients`` of this recipe (task 5),
    ``steps`` are the rows of ``recipe_steps`` and ``nutrition`` is the ``recipe_nutrition``
    row (sprint 3, task 2).  All three stay empty for a recipe created through
    ``POST /recipes``: the structured rows are written by the importer and the page parser
    only, and a manual recipe has neither a source nor a parsed page.
    """
    return {
        "id": row["id"],
        "name": row["recipe_name"],
        "ingredients": row["ingredients"],
        "ingredient_list": list(ingredient_list or []),
        "instructions": row["instruction"],
        "difficulty_level": row["difficulty_level"],
        "source_url": row["source_url"],
        # The default duration of a timer (sprint 3, task 1); null for an imported
        # recipe, because the povarenok dataset has no time at all.
        "cooking_time_minutes": as_int(row.get("cooking_time_minutes")),
        # How many portions the parsed page declares; null when it does not say.
        "servings": as_int(row.get("servings")),
        # Steps as structured rows: user story 6 and the planned step timers build on
        # them, while "instructions" above keeps the same text for older clients.
        "steps": [
            {
                "number": as_int(step["number"]),
                "text": step["text"],
                "image_url": step.get("image_url"),
            }
            for step in (steps or [])
        ],
        "nutrition": _serialize_nutrition(nutrition),
    }


def _serialize_nutrition(nutrition: dict | None) -> dict | None:
    """Serialize a ``recipe_nutrition`` row; every number is optional."""
    if not nutrition:
        return None
    return {
        "calories_total": as_float(nutrition.get("calories_total")),
        "protein_total": as_float(nutrition.get("protein_total")),
        "fat_total": as_float(nutrition.get("fat_total")),
        "carbs_total": as_float(nutrition.get("carbs_total")),
        "calories_per_100g": as_float(nutrition.get("calories_per_100g")),
        "protein_per_100g": as_float(nutrition.get("protein_per_100g")),
        "fat_per_100g": as_float(nutrition.get("fat_per_100g")),
        "carbs_per_100g": as_float(nutrition.get("carbs_per_100g")),
        "source": nutrition.get("source"),
    }


def serialize_timer(row: dict) -> dict:
    """Map a ``timers`` row onto ``components.schemas.Timer``.

    ``remaining_seconds`` and ``server_time`` are computed by the database in the same
    statement (``app/models/timers.py``): the client renders ``ends_at - server_time``
    with a monotonic clock, so the answer never depends on the clock of the device.
    """
    return {
        "id": row["id"],
        "recipe_id": row["recipe_id"],
        "label": row["label"],
        "duration_seconds": as_int(row["duration_seconds"]),
        "started_at": iso_datetime(row["started_at"]),
        "ends_at": iso_datetime(row["ends_at"]),
        "remaining_seconds": as_int(row["remaining_seconds"]),
        "status": row["status"],
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
