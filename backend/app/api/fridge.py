"""Fridge endpoints: ``/fridge_items`` and ``/delete_expired_products``.

Both routes operate on all users exactly as documented in openapi.yaml (the only
enforced rules here are input validation and SQL parameterisation).
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..context import get_db
from ..services import fridge_service
from ..validation import json_array_body

bp = Blueprint("fridge", __name__)


@bp.get("/fridge_items")
def list_items() -> tuple:
    """Return fridge items of every user."""
    return jsonify(fridge_service.list_items(get_db())), 200


@bp.post("/fridge_items")
def add_items() -> tuple:
    """Insert a batch of fridge items."""
    payload = json_array_body()
    return jsonify(fridge_service.add_items(get_db(), payload)), 201


@bp.delete("/delete_expired_products")
def delete_expired_products() -> tuple:
    """Delete expired products of every user."""
    return jsonify(fridge_service.delete_expired_products(get_db())), 200
