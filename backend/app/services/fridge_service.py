"""Fridge contents and expired product removal business logic."""

from __future__ import annotations

import logging

from psycopg2 import errors as pg_errors

from ..db import Database
from ..errors import BadRequest, NotFound
from ..models import fridge as fridge_model
from ..models import users as users_model
from ..serializers import serialize_fridge_item
from ..validation import (
    MAX_PRODUCT_NAME_LENGTH,
    require_date,
    require_positive_int,
    require_string,
)

logger = logging.getLogger(__name__)

MAX_BATCH_SIZE = 100


def list_user_items(db: Database, user_id: int, *, limit: int, offset: int) -> list[dict]:
    """Return one page of the fridge of the token owner (never of another user)."""
    rows = fridge_model.list_user_items_page(db, user_id, limit=limit, offset=offset)
    return [serialize_fridge_item(row) for row in rows]


def add_user_item(db: Database, user_id: int, payload: dict) -> dict:
    """Insert one product into the fridge of ``user_id`` and return the stored item."""
    item = _validated_user_item(payload)
    row = fridge_model.insert_item(db, user_id=user_id, **item)
    return serialize_fridge_item(row)


def delete_user_item(db: Database, user_id: int, item_id: int) -> dict:
    """Delete one item of ``user_id``; a missing or foreign item is the same 404."""
    if not fridge_model.delete_item(db, item_id, user_id):
        raise NotFound(f"Fridge item {item_id} not found")
    return {"message": f"Fridge item {item_id} deleted"}


def delete_user_expired_items(db: Database, user_id: int) -> dict:
    """Delete only the expired products of ``user_id`` (database date is the boundary)."""
    deleted = fridge_model.delete_expired_items(db, user_id=user_id)
    return {"message": f"Deleted {deleted} expired product(s)"}


def list_items(db: Database, *, limit: int, offset: int) -> list[dict]:
    """Return one page of fridge items of all users (openapi.yaml: no token filter)."""
    rows = fridge_model.list_items(db, limit=limit, offset=offset)
    return [serialize_fridge_item(row) for row in rows]


def add_items(db: Database, payload: list) -> dict:
    """Insert a batch of fridge items and return the ``/fridge_items`` POST body."""
    if not payload:
        raise BadRequest("Request body must contain at least one fridge item")
    if len(payload) > MAX_BATCH_SIZE:
        raise BadRequest(f"Request body must contain at most {MAX_BATCH_SIZE} items")
    items = [_validated_item(raw, index) for index, raw in enumerate(payload)]

    requested_user_ids = sorted({item["user_id"] for item in items})
    known_user_ids = users_model.existing_ids(db, requested_user_ids)
    unknown_user_ids = [user_id for user_id in requested_user_ids if user_id not in known_user_ids]
    if unknown_user_ids:
        raise BadRequest(
            f"Unknown user_id(s): {', '.join(str(value) for value in unknown_user_ids)}"
        )

    try:
        inserted = fridge_model.insert_items(db, items)
    except pg_errors.ForeignKeyViolation as exc:
        logger.info("Fridge item batch rejected: unknown user_id")
        raise BadRequest("Unknown user_id in the batch") from exc
    return {"message": f"{inserted} fridge item(s) added"}


def delete_expired_products(db: Database) -> dict:
    """Delete expired items of every user and return the ``/delete_expired_products`` body.

    The rows are selected by the same ``EXPIRED_CONDITION`` (``app/models/fridge.py``) as
    ``/notify_expired``, so the address never deletes something it did not report.
    """
    deleted = fridge_model.delete_expired_items(db)
    return {"message": f"Deleted {deleted} expired product(s)"}


def _validated_user_item(raw: dict) -> dict:
    """Validate the body of ``POST /profile/fridge``; the owner comes from the token."""
    return {
        "product_name": require_string(raw, "product_name", max_length=MAX_PRODUCT_NAME_LENGTH),
        "expiration_date": require_date(raw, "expiration_date"),
        "quantity": require_positive_int(raw, "quantity"),
    }


def _validated_item(raw: object, index: int) -> dict:
    """Validate a single ``FridgeItemInput`` entry, reporting its position on failure."""
    if not isinstance(raw, dict):
        raise BadRequest(f"Item #{index} must be a JSON object")
    try:
        return {
            "user_id": require_positive_int(raw, "user_id"),
            "product_name": require_string(raw, "product_name", max_length=MAX_PRODUCT_NAME_LENGTH),
            "expiration_date": require_date(raw, "expiration_date"),
            "quantity": require_positive_int(raw, "quantity"),
        }
    except BadRequest as exc:
        raise BadRequest(f"Invalid item #{index}: {exc.message}") from exc
