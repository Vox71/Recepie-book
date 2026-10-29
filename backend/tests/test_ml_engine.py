"""Unit tests of the stub recommendation module (``app/ml``) without a database.

The two cases cover the components of ``ml_planning/ml_plan`` that can be checked
without HTTP: preprocessing with the allergen filter, and the KNN ranking with the
fridge bonus.  The endpoint itself is covered by ``tests/test_smart_recommendations.py``.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.ml import engine, knn, preprocessing, vectorizer

MILK_SOUP = {"id": 1, "recipe_name": "Milk soup", "ingredients": "milk, sugar, rice"}
PEANUT_COOKIES = {"id": 2, "recipe_name": "Peanut cookies", "ingredients": "peanuts, flour, sugar"}
TOMATO_SALAD = {"id": 3, "recipe_name": "Tomato salad", "ingredients": "tomato, cucumber, oil"}
MILK_PORRIDGE = {"id": 4, "recipe_name": "Milk porridge", "ingredients": "milk, oats, sugar"}
RECIPES = [MILK_SOUP, PEANUT_COOKIES, TOMATO_SALAD, MILK_PORRIDGE]


def _settings() -> Settings:
    """Settings without the optional ML stack: the module uses the bag-of-words fallback."""
    return Settings({})


def test_preprocessing_normalizes_lemmatizes_and_marks_allergens():
    """Component 1: normalization, stop words, lemmatization and the allergen lookup."""
    assert preprocessing.normalize_text("МолОко, ЯЙЦА!") == "молоко яйца"
    assert preprocessing.tokenize("Milk and sugar, of the rice") == ["milk", "sugar", "rice"]
    # Different forms of the same product must produce the same lemma.
    for left, right in [
        ("яйца", "яйцо"),
        ("молока", "молоко"),
        ("печенье", "печенья"),
        ("peanuts", "peanut"),
        ("tomatoes", "tomato"),
    ]:
        assert preprocessing.lemmatize_terms([left]) == preprocessing.lemmatize_terms([right]), left
    assert preprocessing.lemmatize_terms(["Milk, sugar, rice"]) == ["milk", "sugar", "rice"]
    assert preprocessing.mark_allergens("peanuts, flour, sugar", ["peanut"]) == ["peanut"]
    assert preprocessing.mark_allergens("peanut butter, bread", ["peanut butter"]) == [
        "peanut butter"
    ]
    assert preprocessing.mark_allergens("milk, sugar", ["peanuts"]) == []
    assert preprocessing.mark_allergens("milk, sugar", []) == []


def test_knn_and_the_engine_rank_by_similarity_and_fridge_products():
    """Components 4-6: KNN order, allergen rejection, fridge bonus, limit and cold start."""
    profile = vectorizer.sparse_vector("milk sugar rice")
    candidates = [
        vectorizer.sparse_vector("tomato cucumber oil"),
        vectorizer.sparse_vector("milk sugar rice"),
        vectorizer.sparse_vector("milk oats sugar"),
        vectorizer.sparse_vector("flour sugar"),
    ]
    similarities = [value for _, value in knn.k_nearest(profile, candidates, k=10)]
    assert similarities == sorted(similarities, reverse=True)
    assert similarities[0] == pytest.approx(1.0)
    assert similarities[0] > similarities[1] > similarities[2] > similarities[3]
    assert [index for index, _ in knn.k_nearest(profile, candidates, k=2)] == [1, 2]
    # Equal similarities keep the input order, so the same data always ranks the same.
    duplicate = vectorizer.sparse_vector("sugar rice milk")
    assert [index for index, _ in knn.k_nearest(profile, candidates + [duplicate], k=2)] == [1, 4]

    outcome = engine.recommend_safe_recipes(
        favourites=[MILK_SOUP, TOMATO_SALAD],
        fridge_products=["milk"],
        allergies=["peanuts"],
        recipes=RECIPES,
        limit=5,
        neighbours=10,
        settings=_settings(),
    )
    assert [entry["recipe"]["recipe_name"] for entry in outcome["recipes"]] == [
        "Milk soup",  # similar to the favourites and it uses the milk of the fridge
        "Tomato salad",  # similar to the favourites (it is one of them)
        "Milk porridge",  # similar and in the fridge, but less similar than a favourite
    ]
    assert outcome["stats"] == {
        "favourites_used": 2,
        "fridge_products": 1,
        "allergies_used": 1,
        "candidates": 3,
        "rejected_by_allergy": 1,
        "neighbours": 3,
        "selected": 3,
        "vectorizer": vectorizer.SPARSE_BACKEND,
        "model_documents": None,
        "cold_start": False,
    }
    best = outcome["recipes"][0]
    assert best["recipe"] is MILK_SOUP
    assert best["matched_products"] == ["milk"]
    assert outcome["recipes"][1]["matched_products"] == []

    limited = engine.recommend_safe_recipes(
        favourites=[MILK_SOUP, TOMATO_SALAD],
        fridge_products=["milk"],
        allergies=["peanuts"],
        recipes=RECIPES,
        limit=2,
        neighbours=10,
        settings=_settings(),
    )
    assert [entry["recipe"]["recipe_name"] for entry in limited["recipes"]] == [
        "Milk soup",
        "Tomato salad",
    ]

    cold = engine.recommend_safe_recipes(
        favourites=[],
        fridge_products=["milk"],
        allergies=[],
        recipes=RECIPES,
        limit=5,
        neighbours=10,
        settings=_settings(),
    )
    assert cold["stats"]["cold_start"] is True
    assert cold["stats"]["candidates"] == 4
    # Recipes without a similarity and without a fridge product are not offered.
    assert [entry["recipe"]["recipe_name"] for entry in cold["recipes"]] == [
        "Milk soup",
        "Milk porridge",
    ]
