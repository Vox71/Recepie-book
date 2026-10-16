"""Components 3, 5 and 6 of the stub module: the pipeline itself.

The steps follow the activity diagram of ``ml_planning/image.png``:

1. the favourite recipes of the user form the training sample (component 3);
2. the recipes are preprocessed - normalization, stop words, lemmatization
   (``app.ml.preprocessing``, component 1);
3. the allergens are marked in the recipes and the unsafe ones are rejected
   (filtering, component 5);
4. the training sample and the candidates are vectorized (``app.ml.vectorizer``,
   component 2);
5. the profile vector is the centroid of the training sample; a user without
   favourites is served by the cold start profile built from the fridge;
6. KNN picks the ``neighbours`` most similar recipes (``app.ml.knn``, component 4);
7. the final score adds a bonus for the products already in the fridge
   (context adaptation, component 6);
8. the ``limit`` best recipes with a positive score are returned.

The answer carries the diagnostics that the service layer turns into the message and
the log line, so the API contract stays exactly the one of ``openapi.yaml``.
"""

from __future__ import annotations

import logging
from typing import Sequence

from ..config import Settings
from . import knn, preprocessing, vectorizer

logger = logging.getLogger(__name__)

FRIDGE_BONUS = 0.2
"""Share of the score that the fridge can add; the rest is the KNN similarity."""


def recommend_safe_recipes(
    *,
    favourites: Sequence[dict],
    fridge_products: Sequence[str],
    allergies: Sequence[str],
    recipes: Sequence[dict],
    limit: int,
    neighbours: int,
    settings: Settings,
) -> dict:
    """Run the pipeline and return ``{"recipes": [...], "stats": {...}}``.

    Every entry of ``recipes`` is ``{"recipe": <recipes row>, "similarity": float,
    "score": float, "matched_products": [str]}``.
    """
    sample_texts = _training_sample(favourites)
    cold_start = not sample_texts and bool(fridge_products)
    if cold_start:
        # No favourite yet: the fridge is the only context the module has (component 3).
        sample_texts = [", ".join(fridge_products)]

    safe, rejected = _reject_allergens(recipes, allergies)
    texts = sample_texts + [_ingredients(row) for row in safe]
    vectors, backend = vectorizer.encode_texts(texts, settings)
    profile = vectorizer.centroid(vectors[: len(sample_texts)])
    recipe_vectors = vectors[len(sample_texts) :]

    nearest = knn.k_nearest(profile, recipe_vectors, k=neighbours)
    scored: list[dict] = []
    for index, similarity in nearest:
        row = safe[index]
        matched_products = _matching_products(row, fridge_products)
        share = len(matched_products) / len(fridge_products) if fridge_products else 0.0
        scored.append(
            {
                "recipe": row,
                "similarity": similarity,
                "score": similarity + FRIDGE_BONUS * share,
                "matched_products": matched_products,
            }
        )

    # A recipe without any similarity and without a fridge product is not a
    # recommendation, so it is dropped instead of padding the answer.
    ranked = sorted(scored, key=lambda entry: entry["score"], reverse=True)
    selected = [entry for entry in ranked if entry["score"] > 0][: max(limit, 0)]

    stats = {
        "favourites_used": len(_training_sample(favourites)),
        "fridge_products": len(fridge_products),
        "allergies_used": len(allergies),
        "candidates": len(safe),
        "rejected_by_allergy": rejected,
        "neighbours": len(nearest),
        "selected": len(selected),
        "vectorizer": backend,
        "cold_start": cold_start,
    }
    logger.info(
        "Stub pipeline: %s candidate(s), %s rejected by allergy, %s neighbour(s), "
        "%s selected, vectorizer=%s, cold_start=%s",
        stats["candidates"],
        stats["rejected_by_allergy"],
        stats["neighbours"],
        stats["selected"],
        stats["vectorizer"],
        stats["cold_start"],
    )
    return {"recipes": selected, "stats": stats}


def _ingredients(row: dict) -> str:
    """Ingredient text of a ``recipes`` row (the stub works with ingredients only)."""
    return (row.get("ingredients") or "").strip()


def _training_sample(favourites: Sequence[dict]) -> list[str]:
    """Ingredient texts of the favourite recipes - the training sample (component 3)."""
    return [_ingredients(row) for row in favourites if _ingredients(row)]


def _reject_allergens(recipes: Sequence[dict], allergies: Sequence[str]) -> tuple[list[dict], int]:
    """Drop the recipes that mention an allergy of the user (component 5).

    Returns the safe recipes and the number of rejected ones.
    """
    safe: list[dict] = []
    rejected = 0
    for row in recipes:
        matched = preprocessing.mark_allergens(_ingredients(row), allergies)
        if matched:
            rejected += 1
            logger.info("Recipe %s rejected: allergen(s) %s", row.get("id"), ", ".join(matched))
            continue
        safe.append(row)
    return safe, rejected


def _matching_products(row: dict, products: Sequence[str]) -> list[str]:
    """Products of the fridge that the recipe actually uses (comparison over lemmas)."""
    recipe_lemmas = set(preprocessing.lemmatize_terms([_ingredients(row)]))
    matched: list[str] = []
    for product in products:
        lemmas = preprocessing.lemmatize_terms([product])
        if lemmas and all(lemma in recipe_lemmas for lemma in lemmas):
            matched.append(product)
    return matched
