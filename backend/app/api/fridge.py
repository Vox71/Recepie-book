"""Fridge endpoints: public ``/fridge_items`` and personal ``/profile/fridge``.

The legacy ``/fridge_items`` routes work with all users exactly as documented in
openapi.yaml.  The ``/profile/fridge`` routes are the ones the client uses: the owner is
taken from the token, so the URL and the body can never choose another user
(CONTRIBUTION.md §3).
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..context import get_db
from ..security import current_user_id, token_required
from ..services import fridge_service
from ..validation import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    MAX_PAGE_OFFSET,
    json_array_body,
    json_object_body,
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


@bp.get("/profile/fridge")
@token_required
def list_user_items() -> tuple:
    """Return a page of the fridge of the token owner: ``?limit=&offset=``."""
    limit = query_int("limit", default=DEFAULT_PAGE_LIMIT, minimum=1, maximum=MAX_PAGE_LIMIT)
    offset = query_int("offset", default=0, minimum=0, maximum=MAX_PAGE_OFFSET)
    return (
        jsonify(
            fridge_service.list_user_items(get_db(), current_user_id(), limit=limit, offset=offset)
        ),
        200,
    )


@bp.post("/profile/fridge")
@token_required
def add_user_item() -> tuple:
    """Add one product to the fridge of the token owner."""
    payload = json_object_body()
    return jsonify(fridge_service.add_user_item(get_db(), current_user_id(), payload)), 201


@bp.delete("/profile/fridge/expired")
@token_required
def delete_user_expired_items() -> tuple:
    """Delete only the expired products of the token owner."""
    return (
        jsonify(fridge_service.delete_user_expired_items(get_db(), current_user_id())),
        200,
    )


@bp.delete("/profile/fridge/<int:item_id>")
@token_required
def delete_user_item(item_id: int) -> tuple:
    """Delete one product of the token owner; a foreign id is a 404."""
    return (
        jsonify(fridge_service.delete_user_item(get_db(), current_user_id(), item_id)),
        200,
    )
