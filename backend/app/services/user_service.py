"""User profile (allergies and preferences) business logic."""

from __future__ import annotations

from ..db import Database
from ..errors import BadRequest
from ..models import users as users_model
from ..validation import require_list_of_terms, require_positive_int


def save_preferences(db: Database, payload: dict) -> dict:
    """Replace allergies and preferences of a user (``/user_preferences``).

    openapi.yaml notes that this endpoint is not protected by a token and takes
    ``user_id`` from the request body, therefore the value is validated against
    existing users before it is stored.
    """
    user_id = require_positive_int(payload, "user_id")
    allergies = require_list_of_terms(payload, "allergies", required=False)
    preferences = require_list_of_terms(payload, "preferences", required=False)
    if not users_model.update_user_terms(db, user_id, allergies=allergies, preferences=preferences):
        raise BadRequest(f"User {user_id} does not exist")
    return {"message": "Allergies and preferences updated successfully"}
