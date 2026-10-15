"""User profile endpoint: ``/user_preferences``.

openapi.yaml explicitly documents that this route is not protected by a token and
receives ``user_id`` in the request body, so no ``token_required`` decorator is
applied here (CONTRIBUTION.md §3, §16 would require the opposite).
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..context import get_db
from ..services import user_service
from ..validation import json_object_body

bp = Blueprint("users", __name__)


@bp.post("/user_preferences")
def save_preferences() -> tuple:
    """Store allergies and preferences for ``user_id`` from the body."""
    payload = json_object_body()
    return jsonify(user_service.save_preferences(get_db(), payload)), 200
