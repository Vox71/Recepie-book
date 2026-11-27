"""Timer business logic behind ``/timers`` (sprint 3, task 1).

A user opens a recipe and starts a timer for the time the recipe declares.  The server
stores an absolute deadline (``timers.ends_at``) and answers with the pair
``ends_at``/``server_time``; the client renders ``ends_at - server_time`` with a
monotonic clock, so the countdown does not drift and does not depend on the clock of
the device (docs/timer.md).

The owner is always taken from the token (CONTRIBUTION.md §3): the body cannot choose
``user_id``, and a timer of another user is reported as missing (404).
"""

from __future__ import annotations

from ..db import Database
from ..errors import BadRequest, NotFound
from ..models import recipes as recipes_model
from ..models import timers as timers_model
from ..serializers import iso_datetime, serialize_timer
from ..validation import (
    MAX_ACTIVE_TIMERS,
    MAX_TIMER_DURATION_SECONDS,
    MAX_TIMER_LABEL_LENGTH,
    optional_string,
    require_int_in_range,
    require_positive_int,
)


def _duration_seconds(payload: dict, recipe: dict) -> int:
    """Duration of the timer: the request wins, the recipe time is the fallback.

    ``cooking_time_minutes`` is null for every recipe imported from povarenok (the
    dataset has no time), so for them the client has to send ``duration_seconds``.
    """
    if payload.get("duration_seconds") is not None:
        return require_int_in_range(
            payload, "duration_seconds", minimum=1, maximum=MAX_TIMER_DURATION_SECONDS
        )
    minutes = recipe.get("cooking_time_minutes")
    if minutes is None:
        raise BadRequest(f"Recipe {recipe['id']} has no cooking time, send duration_seconds")
    return int(minutes) * 60


def start_timer(db: Database, user_id: int, payload: dict) -> dict:
    """Start a timer of a recipe of 1..86400 seconds and return ``TimerCreatedResponse``."""
    recipe_id = require_positive_int(payload, "recipe_id")
    recipe = recipes_model.get_recipe(db, recipe_id)
    if recipe is None:
        raise NotFound(f"Recipe {recipe_id} not found")

    duration_seconds = _duration_seconds(payload, recipe)
    # The label is what the user sees in the list of timers; the recipe name is a
    # sensible default, trimmed to the column width.
    label = (
        optional_string(payload, "label", max_length=MAX_TIMER_LABEL_LENGTH)
        or str(recipe["recipe_name"])[:MAX_TIMER_LABEL_LENGTH]
    )

    if timers_model.count_active(db, user_id) >= MAX_ACTIVE_TIMERS:
        raise BadRequest(f"At most {MAX_ACTIVE_TIMERS} timers can run at once")

    row = timers_model.create(db, user_id, recipe_id, label, duration_seconds)
    return {"server_time": iso_datetime(row["server_time"]), "timer": serialize_timer(row)}


def close_expired_timers(db: Database, user_id: int) -> int:
    """Close all expired timers belonging to the specified user.

    Updates expired timers in the database before they are retrieved.
    Timers belonging to other users are not affected.

    Args:
        db: Database connection used to execute the update.
        user_id: ID of the timer owner.

    Returns:
        Number of timers closed during the operation.
    """
    return timers_model.close_expired(db, user_id)

def active_timers(db: Database, user_id: int) -> dict:
    """Retrieve active timers belonging to the specified user.

    This function only reads active timers and does not modify their state.
    Expired timers must be closed by calling ``close_expired_timers()``
    before retrieving the active timers.

    Args:
        db: Database connection used to retrieve timers.
        user_id: ID of the timer owner.

    Returns:
        Dictionary containing server_time and the list of active timers.
    """
    rows = timers_model.list_active(db, user_id, limit=MAX_ACTIVE_TIMERS)
    # The client needs "now" even when no timer is running: it is the reference point
    # for a timer it is about to restore (openapi.yaml, ActiveTimersResponse).
    server_time = rows[0]["server_time"] if rows else timers_model.server_now(db)
    return {
        "server_time": iso_datetime(server_time),
        "timers": [serialize_timer(row) for row in rows],
    }


def cancel_timer(db: Database, user_id: int, timer_id: int) -> dict:
    """Stop a running timer of the token owner or raise 404."""
    if not timers_model.cancel(db, timer_id, user_id):
        raise NotFound(f"Timer {timer_id} not found")
    return {"message": f"Timer {timer_id} cancelled"}
