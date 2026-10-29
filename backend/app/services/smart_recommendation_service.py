"""Service layer of the stub recommendation module.

``recommendation_service.recommend_recipes`` delegates here when
``SMART_RECOMMENDATIONS_ENABLED`` is on, which makes the flag a real switch between the
baseline scoring and the module of ``ml_planning/ml_plan``.  The answer keeps the
contract of ``openapi.yaml`` (``message`` plus ``recipes``), so no API schema changes:

* data of the user: favourites (training sample), fridge (context) and allergies;
* pipeline: ``app.ml.engine`` (preprocessing, vectorization, KNN, filtering);
* every offered recipe is written to ``generated_recipes``, like the baseline path.
"""

from __future__ import annotations

import logging

from ..config import Settings
from ..db import Database
from ..errors import Unauthorized
from ..ml import engine
from ..models import favorites as favorites_model
from ..models import fridge as fridge_model
from ..models import generated as generated_model
from ..models import recipes as recipes_model
from ..models import users as users_model
from ..serializers import serialize_recipe
from ..validation import parse_terms

logger = logging.getLogger(__name__)


def recommend_recipes(db: Database, user_id: int, settings: Settings) -> dict:
    """Recommend recipes with the stub pipeline (favourites + KNN + fridge ranking)."""
    user = users_model.get_user_by_id(db, user_id)
    if user is None:
        raise Unauthorized("User from the token does not exist")

    favourites = favorites_model.list_favorites(db, user_id)
    items = fridge_model.list_user_items(db, user_id)
    if not favourites and not items:
        return {
            "message": "Add favourite recipes or products to your fridge to get recommendations",
            "recipes": [],
        }

    # The normalized table is the source of truth (docs/db_scheme.png); the text column
    # stays a fallback for rows written outside /user_preferences.
    allergies = users_model.list_user_allergies(db, user_id) or parse_terms(user["allergies"])
    outcome = engine.recommend_safe_recipes(
        favourites=favourites,
        fridge_products=[row["product_name"] for row in items],
        allergies=allergies,
        recipes=recipes_model.list_all_recipes(db),
        limit=settings.smart_recommendations_limit,
        neighbours=settings.smart_recommendations_neighbours,
        settings=settings,
    )
    stats = outcome["stats"]
    if not outcome["recipes"]:
        if stats["candidates"] == 0:
            return {"message": "No recipes match your allergies", "recipes": []}
        return {"message": "No recipes similar to your favourites were found", "recipes": []}

    selected = [entry["recipe"] for entry in outcome["recipes"]]
    generated_model.record_generated(db, user_id, [int(row["id"]) for row in selected])
    logger.info(
        "Smart recommendations for user %s: %s candidate(s), %s rejected by allergy, "
        "vectorizer=%s, cold_start=%s",
        user_id,
        stats["candidates"],
        stats["rejected_by_allergy"],
        stats["vectorizer"],
        stats["cold_start"],
    )
    context = (
        "the fridge (cold start, no favourites yet)"
        if stats["cold_start"]
        else f"{stats['favourites_used']} favourite recipe(s) and the fridge"
    )
    return {
        "message": (
            f"Recommended {len(selected)} recipe(s) for {context}: {stats['candidates']} "
            f"candidate(s), {stats['rejected_by_allergy']} rejected by allergy"
        ),
        "recipes": [serialize_recipe(row) for row in selected],
    }
