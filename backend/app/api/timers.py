"""Timer endpoints: ``/timers`` and ``/timers/{id}`` (JWT required).

The user story: "как пользователь, я хочу видеть таймеры в рецепте, чтобы было удобнее
засекать время".  The server owns the deadline, the browser only renders it, so a timer
survives a reload and a second device and never drifts (docs/timer.md).

All routes are personal: the owner is taken from the token only.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..context import get_db
from ..security import current_user_id, token_required
from ..services import timer_service
from ..validation import json_object_body

bp = Blueprint("timers", __name__)


@bp.post("/timers")
@token_required
def start_timer() -> tuple:
    """Start a timer of a recipe: ``duration_seconds`` defaults to the recipe time."""
    payload = json_object_body()
    return jsonify(timer_service.start_timer(get_db(), current_user_id(), payload)), 201


@bp.get("/timers/active")
@token_required
def active_timers() -> tuple:
    """Return the running timers of the token owner together with ``server_time``."""
    return jsonify(timer_service.active_timers(get_db(), current_user_id())), 200


@bp.delete("/timers/<int:timer_id>")
@token_required
def cancel_timer(timer_id: int) -> tuple:
    """Stop a timer of the token owner or return 404."""
    return jsonify(timer_service.cancel_timer(get_db(), current_user_id(), timer_id)), 200
