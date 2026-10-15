"""Recommendation endpoints: ``/suggest_recipes`` and ``/recommend_recipes`` (JWT required)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..context import get_db, get_settings
from ..security import current_user_id, token_required
from ..services import recommendation_service

bp = Blueprint("recommendations", __name__)


@bp.get("/suggest_recipes")
@token_required
def suggest_recipes() -> tuple:
    """Suggest recipes for the expired products of the current user."""
    return (
        jsonify(
            recommendation_service.suggest_recipes(get_db(), current_user_id(), get_settings())
        ),
        200,
    )


@bp.get("/recommend_recipes")
@token_required
def recommend_recipes() -> tuple:
    """Recommend recipes by fridge contents, allergies and preferences."""
    return (
        jsonify(
            recommendation_service.recommend_recipes(get_db(), current_user_id(), get_settings())
        ),
        200,
    )
