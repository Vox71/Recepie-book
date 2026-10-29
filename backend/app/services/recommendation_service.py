"""Recipe suggestions (expired products) and recommendations (fridge + profile)."""

from __future__ import annotations

import logging

from .. import embeddings
from ..config import Settings
from ..db import Database
from ..errors import Unauthorized
from ..models import fridge as fridge_model
from ..models import generated as generated_model
from ..models import recipes as recipes_model
from ..models import users as users_model
from ..validation import has_any_term, parse_terms
from . import allergen_service, smart_recommendation_service
from .recipe_presenter import present_recipes

logger = logging.getLogger(__name__)

PREFERENCE_BONUS = 0.2
EMBEDDING_ERRORS = (ImportError, OSError, RuntimeError, ValueError)


def suggest_recipes(db: Database, user_id: int, settings: Settings) -> dict:
    """Suggest recipes that use up the expired products of the current user."""
    expired_rows = fridge_model.list_expired_items(db, user_id=user_id)
    if not expired_rows:
        return {"message": "No expired products found, nothing to suggest"}

    patterns = [f"%{row['product_name']}%" for row in expired_rows]
    found = recipes_model.find_recipes_with_ingredients(
        db, patterns, limit=settings.recommendations_limit
    )
    if not found:
        return {"message": "No recipes found for your expired products"}
    generated_model.record_generated(db, user_id, [int(row["id"]) for row in found])
    return {
        "message": f"Found {len(found)} recipe(s) to use up your expired products",
        "recipes": present_recipes(db, found),
    }


def recommend_recipes(db: Database, user_id: int, settings: Settings) -> dict:
    """Recommend recipes based on the fridge contents, allergies and preferences.

    With ``SMART_RECOMMENDATIONS_ENABLED`` the request is served by the stub ML module
    (``app/ml``), otherwise by the baseline scoring below; the answer has the same shape
    in both cases (openapi.yaml), so a client cannot tell the modes apart.
    """
    if settings.smart_recommendations_enabled:
        return smart_recommendation_service.recommend_recipes(db, user_id, settings)

    user = users_model.get_user_by_id(db, user_id)
    if user is None:
        raise Unauthorized("User from the token does not exist")

    items = fridge_model.list_user_items(db, user_id)
    if not items:
        return {
            "message": "Your fridge is empty, add products to get recommendations",
            "recipes": [],
        }

    # The normalized table is the source of truth (docs/db_scheme.png); the text
    # column is kept as a fallback for rows written outside /user_preferences.
    allergies = users_model.list_user_allergies(db, user_id) or parse_terms(user["allergies"])
    preferences = parse_terms(user["preferences"])
    # The allergen filter reads recipe_ingredients (app/services/allergen_service.py), so
    # "кокосовое молоко" is not taken for milk and "гречневая мука" is not gluten.
    candidates, _rejected_by_allergy = allergen_service.filter_safe_recipes(
        db, recipes_model.list_all_recipes(db), allergies
    )
    if not candidates:
        return {"message": "No recipes match your allergies", "recipes": []}

    product_names = [row["product_name"] for row in items]
    scores = _score_candidates(candidates, product_names, preferences, settings)
    ranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)
    matched = [(row, score) for row, score in ranked if score > 0]
    if not matched:
        return {"message": "No recipes matching your fridge were found", "recipes": []}

    selected = matched[: settings.recommendations_limit]
    generated_model.record_generated(db, user_id, [int(row["id"]) for row, _ in selected])
    return {
        "message": f"Recommended {len(selected)} recipe(s) based on your fridge, "
        "allergies and preferences",
        "recipes": present_recipes(db, [row for row, _ in selected]),
    }


def _score_candidates(
    candidates: list[dict], product_names: list[str], preferences: list[str], settings: Settings
) -> list[float]:
    """Score candidates with embeddings when enabled, otherwise with keyword overlap."""
    if settings.embeddings_enabled and embeddings.is_available():
        try:
            return _semantic_scores(candidates, product_names, preferences, settings)
        except EMBEDDING_ERRORS:
            logger.warning(
                "Embedding scoring failed, falling back to keyword scoring", exc_info=True
            )
    return [_keyword_score(row, product_names, preferences) for row in candidates]


def _semantic_scores(
    candidates: list[dict], product_names: list[str], preferences: list[str], settings: Settings
) -> list[float]:
    """Cosine similarity between the fridge profile and each recipe."""
    query_text = ", ".join(product_names + preferences)
    texts = [query_text] + [row["ingredients"] for row in candidates]
    vectors = embeddings.encode(texts, settings.embedding_model)
    similarities = embeddings.cosine_similarity(vectors[0], vectors[1:])
    return [
        similarity + (PREFERENCE_BONUS if has_any_term(row["ingredients"], preferences) else 0.0)
        for row, similarity in zip(candidates, similarities)
    ]


def _keyword_score(row: dict, product_names: list[str], preferences: list[str]) -> float:
    """Share of fridge products mentioned in the recipe, plus a preference bonus."""
    if not product_names:
        return 0.0
    ingredients = row["ingredients"].lower()
    matched = sum(1 for name in product_names if name.lower() in ingredients)
    score = matched / len(product_names)
    if has_any_term(row["ingredients"], preferences):
        score += PREFERENCE_BONUS
    return score
