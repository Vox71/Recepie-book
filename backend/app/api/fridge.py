"""Fridge endpoints: ``/fridge_items`` and ``/delete_expired_products``.

Both routes operate on all users exactly as documented in openapi.yaml (the only
enforced rules here are input validation and SQL parameterisation).
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..context import get_db
from ..services import fridge_service
from ..validation import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    MAX_PAGE_OFFSET,
    json_array_body,
    query_int,
)

bp = Blueprint("fridge", __name__)


@bp.get("/fridge_items")
def list_items() -> tuple:
    """Return a page of fridge items of every user: ``?limit=&offset=``."""
    limit = query_int("limit", default=DEFAULT_PAGE_LIMIT, minimum=1, maximum=MAX_PAGE_LIMIT)
    offset = query_int("offset", default=0, minimum=0, maximum=MAX_PAGE_OFFSET)
    return jsonify(fridge_service.list_items(get_db(), limit=limit, offset=offset)), 200


@bp.post("/fridge_items")
def add_items() -> tuple:
    """Insert a batch of fridge items."""
    payload = json_array_body()
    return jsonify(fridge_service.add_items(get_db(), payload)), 201


@bp.delete("/delete_expired_products")
def delete_expired_products() -> tuple:
    """Delete expired products of every user."""
    return jsonify(fridge_service.delete_expired_products(get_db())), 200
