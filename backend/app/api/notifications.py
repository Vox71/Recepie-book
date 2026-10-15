"""Notification endpoints: ``/notify_expired`` and ``/delete_expired`` (JWT required)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..context import get_db
from ..security import current_user_id, token_required
from ..services import notification_service

bp = Blueprint("notifications", __name__)


@bp.get("/notify_expired")
@token_required
def notify_expired() -> tuple:
    """Report expired products of the current user."""
    return jsonify(notification_service.notify_expired(get_db(), current_user_id())), 200


@bp.delete("/delete_expired")
@token_required
def delete_expired() -> tuple:
    """Delete expired products of the current user."""
    return jsonify(notification_service.delete_expired(get_db(), current_user_id())), 200
