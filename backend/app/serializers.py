"""Serialization helpers.

Rows coming from PostgreSQL contain ``date``, ``datetime`` and ``Decimal``
objects, while openapi.yaml declares ISO 8601 strings and JSON numbers.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def iso_date(value: date | None) -> str | None:
    """Serialize a ``date`` as ``YYYY-MM-DD``."""
    return value.isoformat() if value is not None else None


def iso_datetime(value: datetime | None) -> str | None:
    """Serialize a ``datetime`` in ISO 8601 (with offset when available)."""
    return value.isoformat() if value is not None else None


def as_number(value: Any) -> float | None:
    """Serialize a numeric column value as a JSON number."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def serialize_recipe(row: dict) -> dict:
    """Map a ``recipes`` row onto ``components.schemas.Recipe``."""
    return {
        "id": row["id"],
        "name": row["name"],
        "ingredients": row["ingredients"],
        "instructions": row["instructions"],
        "cuisine_type": row["cuisine_type"],
        "difficulty_level": row["difficulty_level"],
    }


def serialize_fridge_item(row: dict) -> dict:
    """Map a ``fridge_items`` row onto ``components.schemas.FridgeItem``."""
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "product_name": row["product_name"],
        "expiration_date": iso_date(row["expiration_date"]),
        "quantity": as_number(row["quantity"]),
        "last_added": iso_datetime(row["last_added"]),
    }


def serialize_expired_product(row: dict) -> dict:
    """Map a ``fridge_items`` row onto the ``expired_products`` item schema."""
    return {
        "id": row["id"],
        "name": row["product_name"],
        "expiration_date": iso_date(row["expiration_date"]),
    }
