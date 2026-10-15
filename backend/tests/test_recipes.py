"""Recipe CRUD contract tests: ``/recipes`` and ``/recipes/{id}``."""

from __future__ import annotations

import pytest

RECIPE_PAYLOAD = {
    "name": "Tomato pasta",
    "ingredients": "pasta, tomato, cheese, olive oil",
    "instructions": "Boil the pasta, mix with tomato and cheese.",
    "cuisine_type": "italian",
    "difficulty_level": "easy",
}


@pytest.mark.parametrize(
    "missing_field",
    ["name", "ingredients", "instructions", "cuisine_type", "difficulty_level"],
)
def test_create_recipe_requires_all_fields(db_client, missing_field):
    payload = {key: value for key, value in RECIPE_PAYLOAD.items() if key != missing_field}
    response = db_client.post("/recipes", json=payload)
    assert response.status_code == 400
    assert missing_field in response.get_json()["error"]


def test_create_recipe_rejects_wrong_types(db_client):
    response = db_client.post("/recipes", json={**RECIPE_PAYLOAD, "name": ["not", "a", "string"]})
    assert response.status_code == 400


def test_create_recipe_does_not_require_a_token(db_client):
    """openapi.yaml documents that token checking is disabled for ``POST /recipes``."""
    response = db_client.post("/recipes", json=RECIPE_PAYLOAD)
    assert response.status_code == 201
    assert "message" in response.get_json()


def test_create_and_read_recipes(db_client):
    assert db_client.post("/recipes", json=RECIPE_PAYLOAD).status_code == 201

    listed = db_client.get("/recipes")
    assert listed.status_code == 200
    recipes = listed.get_json()
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe == {"id": recipe["id"], **RECIPE_PAYLOAD}
    assert isinstance(recipe["id"], int)

    fetched = db_client.get(f"/recipes/{recipe['id']}")
    assert fetched.status_code == 200
    assert fetched.get_json() == recipe


def test_get_unknown_recipe_returns_404(db_client):
    response = db_client.get("/recipes/424242")
    assert response.status_code == 404
    assert "424242" in response.get_json()["error"]


def test_update_recipe(db_client):
    db_client.post("/recipes", json=RECIPE_PAYLOAD)
    recipe_id = db_client.get("/recipes").get_json()[0]["id"]

    updated_payload = {**RECIPE_PAYLOAD, "name": "Spicy pasta", "difficulty_level": "medium"}
    response = db_client.put(f"/recipes/{recipe_id}", json=updated_payload)
    assert response.status_code == 200
    assert "message" in response.get_json()

    stored = db_client.get(f"/recipes/{recipe_id}").get_json()
    assert stored["name"] == "Spicy pasta"
    assert stored["difficulty_level"] == "medium"


def test_update_recipe_validates_the_body(db_client):
    db_client.post("/recipes", json=RECIPE_PAYLOAD)
    recipe_id = db_client.get("/recipes").get_json()[0]["id"]
    assert db_client.put(f"/recipes/{recipe_id}", json={"name": "only name"}).status_code == 400


def test_update_unknown_recipe_returns_404(db_client):
    response = db_client.put("/recipes/424242", json=RECIPE_PAYLOAD)
    assert response.status_code == 404


def test_delete_recipe(db_client):
    db_client.post("/recipes", json=RECIPE_PAYLOAD)
    recipe_id = db_client.get("/recipes").get_json()[0]["id"]

    deleted = db_client.delete(f"/recipes/{recipe_id}")
    assert deleted.status_code == 200
    assert "message" in deleted.get_json()
    assert db_client.get(f"/recipes/{recipe_id}").status_code == 404
    assert db_client.get("/recipes").get_json() == []


def test_delete_unknown_recipe_returns_404(db_client):
    assert db_client.delete("/recipes/424242").status_code == 404
