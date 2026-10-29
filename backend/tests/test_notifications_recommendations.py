"""``/notify_expired``, ``/delete_expired``, ``/suggest_recipes``, ``/recommend_recipes``.

All four routes require a JWT token: the user is taken from the token and never
from the request body.
"""

from __future__ import annotations

from datetime import date, timedelta

YESTERDAY = date.today() - timedelta(days=1)
TOMORROW = date.today() + timedelta(days=1)

MILK_RECIPE = {
    "name": "Milk soup",
    "ingredients": "milk, sugar, rice",
    "instructions": "Cook everything together.",
    "difficulty_level": "easy",
}
PEANUT_RECIPE = {
    "name": "Peanut cookies",
    "ingredients": "peanuts, flour, sugar",
    "instructions": "Bake the cookies.",
    "difficulty_level": "medium",
}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_all_four_routes_require_a_token(client):
    for method, path in [
        ("get", "/notify_expired"),
        ("delete", "/delete_expired"),
        ("get", "/suggest_recipes"),
        ("get", "/recommend_recipes"),
    ]:
        call = getattr(client, method)
        assert call(path).status_code == 401, path
        assert call(path, headers=_auth("not-a-valid-token")).status_code == 401, path


def test_notify_expired_lists_only_expired_products(db_client, register_user, add_fridge_items):
    user_id, token = register_user()

    empty = db_client.get("/notify_expired", headers=_auth(token))
    assert empty.status_code == 200
    assert empty.get_json() == {"message": "No expired products found"}

    add_fridge_items(user_id, "sour milk", YESTERDAY)
    add_fridge_items(user_id, "fresh bread", TOMORROW)

    response = db_client.get("/notify_expired", headers=_auth(token))
    assert response.status_code == 200
    body = response.get_json()
    assert [product["name"] for product in body["expired_products"]] == ["sour milk"]
    expired = body["expired_products"][0]
    assert expired["expiration_date"] == YESTERDAY.isoformat()
    assert isinstance(expired["id"], int)


def test_delete_expired_touches_only_the_user_from_the_token(
    db_client, register_user, add_fridge_items
):
    first, first_token = register_user(email="first@example.com")
    second, _ = register_user(email="second@example.com")
    add_fridge_items(first, "old milk", YESTERDAY)
    add_fridge_items(second, "old bread", YESTERDAY)

    response = db_client.delete("/delete_expired", headers=_auth(first_token))
    assert response.status_code == 200
    assert response.get_json() == {"message": "Deleted 1 expired product(s)"}

    remaining = [item["product_name"] for item in db_client.get("/fridge_items").get_json()]
    assert remaining == ["old bread"]


def test_notify_expired_and_delete_expired_products_use_one_rule(
    db_client, register_user, add_relative_fridge_items
):
    """Both addresses share one predicate: what is reported is exactly what is deleted."""
    user_id, token = register_user()
    add_relative_fridge_items(user_id, "sour milk", -1)
    add_relative_fridge_items(user_id, "expires today", 0)
    add_relative_fridge_items(user_id, "fresh bread", 1)

    notify = db_client.get("/notify_expired", headers=_auth(token))
    assert notify.status_code == 200
    reported = [product["name"] for product in notify.get_json()["expired_products"]]
    assert reported == ["sour milk"]

    response = db_client.delete("/delete_expired_products")
    assert response.status_code == 200
    assert response.get_json() == {"message": f"Deleted {len(reported)} expired product(s)"}

    # A product that expires today is still usable, so the deletion keeps it as well.
    remaining = {item["product_name"] for item in db_client.get("/fridge_items").get_json()}
    assert remaining == {"expires today", "fresh bread"}

    # Nothing is left to report: the notification and the deletion look at the same rows.
    after = db_client.get("/notify_expired", headers=_auth(token))
    assert after.get_json() == {"message": "No expired products found"}


def test_suggest_recipes_uses_the_expired_products(db_client, register_user, add_fridge_items, db):
    user_id, token = register_user()
    db_client.post("/recipes", json=MILK_RECIPE)
    db_client.post("/recipes", json=PEANUT_RECIPE)

    # Nothing expired yet: the answer has no recipes at all.
    empty = db_client.get("/suggest_recipes", headers=_auth(token))
    assert empty.status_code == 200
    assert empty.get_json() == {"message": "No expired products found, nothing to suggest"}

    add_fridge_items(user_id, "milk", YESTERDAY)

    response = db_client.get("/suggest_recipes", headers=_auth(token))
    assert response.status_code == 200
    body = response.get_json()
    assert body["message"]
    # Only the recipe whose ingredients mention the expired product is offered.
    assert [recipe["name"] for recipe in body["recipes"]] == ["Milk soup"]
    # Task 5: every recipe of an answer follows components.schemas.Recipe.
    assert set(body["recipes"][0]) == {
        "id",
        "name",
        "ingredients",
        "ingredient_list",
        "instructions",
        "difficulty_level",
        "source_url",
    }

    # generated_recipes keeps what was offered (docs/db_scheme.png).
    rows = db.fetch_all(
        """
        SELECT r.recipe_name
        FROM generated_recipes AS g
        JOIN recipes AS r ON r.id = g.recipes_id
        WHERE g.user_id = %s
        """,
        (user_id,),
    )
    assert [row["recipe_name"] for row in rows] == ["Milk soup"]


def test_recommend_recipes_uses_the_fridge_and_skips_the_allergies(
    db_client, register_user, add_fridge_items, db
):
    user_id, token = register_user()
    db_client.post("/recipes", json=MILK_RECIPE)
    db_client.post("/recipes", json=PEANUT_RECIPE)
    db_client.post("/user_preferences", json={"user_id": user_id, "allergies": ["peanuts"]})
    add_fridge_items(user_id, "milk", TOMORROW)

    response = db_client.get("/recommend_recipes", headers=_auth(token))
    assert response.status_code == 200
    body = response.get_json()
    assert body["message"]
    # Peanut cookies are excluded because of the allergy, Milk soup matches the fridge.
    assert [recipe["name"] for recipe in body["recipes"]] == ["Milk soup"]

    # The offered recipes are stored in generated_recipes.
    rows = db.fetch_all(
        "SELECT recipes_id, generated_on FROM generated_recipes WHERE user_id = %s", (user_id,)
    )
    assert len(rows) == 1
    assert rows[0]["recipes_id"] is not None
    assert rows[0]["generated_on"] is not None

    # An empty fridge gives an empty list, an unknown user gives 401.
    empty_user_id, empty_token = register_user(email="empty@example.com")
    assert empty_user_id != user_id
    empty = db_client.get("/recommend_recipes", headers=_auth(empty_token))
    assert empty.status_code == 200
    assert empty.get_json()["recipes"] == []

    # Allergies written straight into users.allergies (no normalized rows) still count.
    db.execute("UPDATE users SET allergies = %s WHERE id = %s", ("peanuts", empty_user_id))
    add_fridge_items(empty_user_id, "milk", TOMORROW)
    fallback = db_client.get("/recommend_recipes", headers=_auth(empty_token))
    assert [recipe["name"] for recipe in fallback.get_json()["recipes"]] == ["Milk soup"]
