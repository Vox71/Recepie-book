"""Tests for ``/notify_expired``, ``/delete_expired``, ``/suggest_recipes`` and
``/recommend_recipes``."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import jwt
import pytest

YESTERDAY = date.today() - timedelta(days=1)
TOMORROW = date.today() + timedelta(days=1)

MILK_RECIPE = {
    "name": "Milk soup",
    "ingredients": "milk, sugar, rice",
    "instructions": "Cook everything together.",
    "cuisine_type": "russian",
    "difficulty_level": "easy",
}
PEANUT_RECIPE = {
    "name": "Peanut cookies",
    "ingredients": "peanuts, flour, sugar",
    "instructions": "Bake the cookies.",
    "cuisine_type": "american",
    "difficulty_level": "medium",
}


@pytest.mark.parametrize("path", ["/notify_expired", "/suggest_recipes", "/recommend_recipes"])
def test_get_endpoints_require_a_token(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_delete_expired_requires_a_token(client):
    assert client.delete("/delete_expired").status_code == 401


def test_notify_expired_without_products(db_client, auth_headers):
    response = db_client.get("/notify_expired", headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json() == {"message": "No expired products found"}


def test_notify_expired_lists_the_products(db_client, register_user, add_fridge_items):
    user_id, token = register_user()
    add_fridge_items(user_id, "sour milk", YESTERDAY)
    add_fridge_items(user_id, "fresh bread", TOMORROW)

    response = db_client.get("/notify_expired", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    body = response.get_json()
    assert body["message"]
    assert [product["name"] for product in body["expired_products"]] == ["sour milk"]
    expired = body["expired_products"][0]
    assert expired["expiration_date"] == YESTERDAY.isoformat()
    assert isinstance(expired["id"], int)


def test_delete_expired_touches_only_the_current_user(db_client, register_user, add_fridge_items):
    first, first_token = register_user(email="first@example.com")
    second, _ = register_user(email="second@example.com")
    add_fridge_items(first, "old milk", YESTERDAY)
    add_fridge_items(second, "old bread", YESTERDAY)

    response = db_client.delete(
        "/delete_expired", headers={"Authorization": f"Bearer {first_token}"}
    )
    assert response.status_code == 200
    assert response.get_json()["message"] == "Deleted 1 expired product(s)"

    remaining = [item["product_name"] for item in db_client.get("/fridge_items").get_json()]
    assert remaining == ["old bread"]


def test_suggest_recipes_uses_expired_products(db_client, register_user, add_fridge_items):
    user_id, token = register_user()
    db_client.post("/recipes", json=MILK_RECIPE)
    db_client.post("/recipes", json=PEANUT_RECIPE)
    add_fridge_items(user_id, "milk", YESTERDAY)

    response = db_client.get("/suggest_recipes", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.get_json()
    assert [recipe["name"] for recipe in body["recipes"]] == ["Milk soup"]
    assert body["message"]


def test_suggest_recipes_without_expired_products(db_client, auth_headers):
    response = db_client.get("/suggest_recipes", headers=auth_headers())
    assert response.status_code == 200
    body = response.get_json()
    assert body["message"]
    assert "recipes" not in body


def test_recommend_recipes_skips_allergy_ingredients(db_client, register_user, add_fridge_items):
    user_id, token = register_user()
    db_client.post("/recipes", json=MILK_RECIPE)
    db_client.post("/recipes", json=PEANUT_RECIPE)
    db_client.post(
        "/user_preferences",
        json={"user_id": user_id, "allergies": ["peanuts"], "preferences": []},
    )
    add_fridge_items(user_id, "milk", TOMORROW)

    response = db_client.get("/recommend_recipes", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.get_json()
    assert [recipe["name"] for recipe in body["recipes"]] == ["Milk soup"]


def test_recommend_recipes_with_an_empty_fridge(db_client, auth_headers):
    response = db_client.get("/recommend_recipes", headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json()["recipes"] == []


def test_recommend_recipes_rejects_a_token_of_an_unknown_user(db_client, jwt_secret):
    token = jwt.encode(
        {"sub": "424242", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        jwt_secret,
        algorithm="HS256",
    )
    response = db_client.get("/recommend_recipes", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
