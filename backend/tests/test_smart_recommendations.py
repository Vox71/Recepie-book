"""``/recommend_recipes`` in both modes of ``SMART_RECOMMENDATIONS_ENABLED``.

The flag switches the endpoint between the baseline scoring and the stub ML module
(``app/ml``), so the same data has to produce the baseline answer with the flag off and
the favourites driven answer with the flag on.  Both applications share one database and
differ in that single environment variable only (``db_app_factory`` in ``conftest``).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models import favorites as favorites_model
from app.models import generated as generated_model

TOMORROW = date.today() + timedelta(days=1)

MILK_SOUP = {
    "name": "Milk soup",
    "ingredients": "milk, sugar, rice",
    "instructions": "Cook everything together.",
    "difficulty_level": "easy",
}
PEANUT_COOKIES = {
    "name": "Peanut cookies",
    "ingredients": "peanuts, flour, sugar",
    "instructions": "Bake the cookies.",
    "difficulty_level": "medium",
}
TOMATO_SALAD = {
    "name": "Tomato salad",
    "ingredients": "tomato, cucumber, oil",
    "instructions": "Chop the vegetables and mix.",
    "difficulty_level": "easy",
}
MILK_PORRIDGE = {
    "name": "Milk porridge",
    "ingredients": "milk, oats, sugar",
    "instructions": "Boil the oats in milk.",
    "difficulty_level": "easy",
}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def smart_client(db_app_factory):
    """HTTP client of the same database, but with the stub module switched on."""
    return db_app_factory(SMART_RECOMMENDATIONS_ENABLED="true").test_client()


def _create_recipes(client, *recipes: dict) -> None:
    for recipe in recipes:
        response = client.post("/recipes", json=recipe)
        assert response.status_code == 201, response.get_json()


def _recipe_ids(db) -> dict[str, int]:
    """Map the recipe name onto its id (favourites are stored by id)."""
    return {
        row["recipe_name"]: int(row["id"])
        for row in db.fetch_all("SELECT id, recipe_name FROM recipes")
    }


def _prepare_profile(db_client, db, register_user, add_fridge_items, *, favourites: bool):
    """Create the user, the recipes, the allergy and the fridge used by the cases."""
    user_id, token = register_user()
    _create_recipes(db_client, MILK_SOUP, PEANUT_COOKIES, TOMATO_SALAD, MILK_PORRIDGE)
    response = db_client.post(
        "/user_preferences", json={"user_id": user_id, "allergies": ["peanuts"]}
    )
    assert response.status_code == 200, response.get_json()
    if favourites:
        # favourite_recipes has no address in openapi.yaml, so the rows go in directly.
        ids = _recipe_ids(db)
        assert favorites_model.add_favorite(db, user_id, ids["Milk soup"]) is True
        assert favorites_model.add_favorite(db, user_id, ids["Tomato salad"]) is True
    add_fridge_items(user_id, "milk", TOMORROW)
    return user_id, token


def test_the_flag_on_ranks_the_favourites_and_the_fridge(
    smart_client, db_client, register_user, add_fridge_items, db
):
    """With the flag on the answer comes from the stub module, contract unchanged."""
    user_id, token = _prepare_profile(
        db_client, db, register_user, add_fridge_items, favourites=True
    )

    response = smart_client.get("/recommend_recipes", headers=_auth(token))
    assert response.status_code == 200
    body = response.get_json()
    # openapi.yaml.Recommendation: message + recipes, nothing else (no score leaks).
    assert set(body) == {"message", "recipes"}
    ids = _recipe_ids(db)
    assert [recipe["name"] for recipe in body["recipes"]] == [
        "Milk soup",  # a favourite and it uses the milk from the fridge
        "Tomato salad",  # a favourite, similar to the profile without any fridge product
        "Milk porridge",  # similar and in the fridge, but not a favourite
    ]
    assert [recipe["id"] for recipe in body["recipes"]] == [
        ids["Milk soup"],
        ids["Tomato salad"],
        ids["Milk porridge"],
    ]
    # Peanut cookies are filtered out by the allergy, which the message reports.
    assert "rejected by allergy" in body["message"]
    # Everything that was offered is audited in generated_recipes.
    assert len(generated_model.list_generated(db, user_id)) == 3


def test_the_flag_off_keeps_the_baseline_answer(db_client, register_user, add_fridge_items, db):
    """With the flag off the endpoint behaves exactly as before the module."""
    _, token = _prepare_profile(db_client, db, register_user, add_fridge_items, favourites=True)

    response = db_client.get("/recommend_recipes", headers=_auth(token))
    assert response.status_code == 200
    body = response.get_json()
    # The baseline path scores the fridge only, so the favourite salad is not offered -
    # while the same data with the flag on returns it (the case above).
    assert [recipe["name"] for recipe in body["recipes"]] == ["Milk soup", "Milk porridge"]
    assert set(body) == {"message", "recipes"}


def test_smart_mode_answers_an_empty_profile_and_rejects_an_unknown_user(
    smart_client, register_user, db
):
    """No favourites and no fridge is a valid request; a deleted user stays a 401."""
    user_id, token = register_user()

    empty = smart_client.get("/recommend_recipes", headers=_auth(token))
    assert empty.status_code == 200
    assert empty.get_json()["recipes"] == []
    assert empty.get_json()["message"]

    # A signed token of a user that no longer exists is rejected, as in the baseline.
    assert db.execute("DELETE FROM users WHERE id = %s", (user_id,)) == 1
    gone = smart_client.get("/recommend_recipes", headers=_auth(token))
    assert gone.status_code == 401
    assert gone.get_json() == {"error": "User from the token does not exist"}
