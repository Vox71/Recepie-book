"""Notification business logic for expired products.

"Expired" is defined once, in ``app/models/fridge.py`` (``EXPIRED_CONDITION``), so
``/notify_expired`` and ``DELETE /delete_expired_products`` never disagree.
"""

from __future__ import annotations

from ..db import Database
from ..models import fridge as fridge_model
from ..serializers import serialize_expired_product


def expired_products(db: Database, user_id: int) -> list[dict]:
    """Return expired products of a single user, ready for JSON."""
    rows = fridge_model.list_expired_items(db, user_id=user_id)
    return [serialize_expired_product(row) for row in rows]


def notify_expired(db: Database, user_id: int) -> dict:
    """Build the ``/notify_expired`` response body for one user."""
    products = expired_products(db, user_id)
    if not products:
        return {"message": "No expired products found"}
    return {
        "message": f"You have {len(products)} expired product(s): "
        + ", ".join(product["name"] for product in products),
        "expired_products": products,
    }


def delete_expired(db: Database, user_id: int) -> dict:
    """Delete expired products of a single user."""
    deleted = fridge_model.delete_expired_items(db, user_id=user_id)
    return {"message": f"Deleted {deleted} expired product(s)"}
