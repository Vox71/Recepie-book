"""Favourites: ``/favorite_recipes`` (list, add) and ``/favorite_recipes/{id}`` (remove).

All three routes are personal: the owner comes from the token, so the body and the URL
cannot choose another user (CONTRIBUTION.md §3).  The list is newest first — the order
of ``favorite_recipes.created_at`` — and adding the same recipe twice changes nothing.
"""

from __future__ import annotations

RECIPE = {
    "name": "Tomato pasta",
    "ingredients": "pasta, tomato, cheese, olive oil",
    "instructions": "Boil the pasta, mix with tomato and cheese.",
    "difficulty_level": "easy",
}


def _auth(token: str) -> dict:
    """Headers of an authenticated request."""
    return {"Authorization": f"Bearer {token}"}


def _create_recipe(client, name: str) -> int:
    """Create a recipe through the API and return its id."""
    response = client.post("/recipes", json={**RECIPE, "name": name})
    assert response.status_code == 201, response.get_json()
    return {recipe["name"]: recipe["id"] for recipe in client.get("/recipes").get_json()}[name]


def test_add_list_and_remove_favourites(db_client, register_user, db):
    """Newest first, idempotent add, and the row disappears after ``DELETE``."""
    _, token = register_user()
    _, other_token = register_user(email="other@example.com")
    first = _create_recipe(db_client, "Tomato pasta")
    second = _create_recipe(db_client, "Spinach soup")

    # user_id comes from the token: the field in the body is ignored, so the favourite
    # belongs to the token owner and the other user stays empty.
    response = db_client.post(
        "/favorite_recipes",
        json={"recipe_id": first, "user_id": 999999},
        headers=_auth(token),
    )
    assert response.status_code == 201
    assert response.get_json() == {"message": f"Recipe {first} added to favourites"}

    # A repeat is idempotent: no duplicate row, no error, the message says "already".
    repeat = db_client.post("/favorite_recipes", json={"recipe_id": first}, headers=_auth(token))
    assert repeat.status_code == 201
    assert repeat.get_json() == {"message": f"Recipe {first} is already in favourites"}
    assert db.fetch_one("SELECT count(*) AS rows FROM favorite_recipes")["rows"] == 1

    assert (
        db_client.post(
            "/favorite_recipes", json={"recipe_id": second}, headers=_auth(token)
        ).status_code
        == 201
    )

    listed = db_client.get("/favorite_recipes", headers=_auth(token))
    assert listed.status_code == 200
    assert [recipe["id"] for recipe in listed.get_json()] == [second, first]  # newest first
    assert listed.get_json()[0] == {"id": second, **{**RECIPE, "name": "Spinach soup"}}
    assert db_client.get("/favorite_recipes", headers=_auth(other_token)).get_json() == []

    removed = db_client.delete(f"/favorite_recipes/{first}", headers=_auth(token))
    assert removed.status_code == 200
    assert removed.get_json() == {"message": f"Recipe {first} removed from favourites"}
    remaining = db_client.get("/favorite_recipes", headers=_auth(token)).get_json()
    assert [recipe["id"] for recipe in remaining] == [second]


def test_favourite_routes_require_a_token(db_client):
    """Favourites are personal, so a missing or broken token is a 401 (not an empty list)."""
    recipe_id = _create_recipe(db_client, "Tomato pasta")

    without_token = [
        db_client.get("/favorite_recipes"),
        db_client.post("/favorite_recipes", json={"recipe_id": recipe_id}),
        db_client.delete(f"/favorite_recipes/{recipe_id}"),
    ]
    for response in without_token:
        assert response.status_code == 401
        assert "error" in response.get_json()

    broken = db_client.get("/favorite_recipes", headers={"Authorization": "Bearer not-a-token"})
    assert broken.status_code == 401
    assert "error" in broken.get_json()


def test_favourites_of_another_user_are_invisible(db_client, register_user, db):
    """A second user neither sees nor removes the favourites of the first one."""
    _, owner_token = register_user()
    _, other_token = register_user(email="other@example.com")
    recipe_id = _create_recipe(db_client, "Tomato pasta")
    assert (
        db_client.post(
            "/favorite_recipes", json={"recipe_id": recipe_id}, headers=_auth(owner_token)
        ).status_code
        == 201
    )

    assert db_client.get("/favorite_recipes", headers=_auth(other_token)).get_json() == []

    # 404 rather than 403: for this user the row does not exist, so the answer does not
    # disclose that somebody else has this recipe in the favourites.
    response = db_client.delete(f"/favorite_recipes/{recipe_id}", headers=_auth(other_token))
    assert response.status_code == 404
    assert str(recipe_id) in response.get_json()["error"]

    assert db.fetch_one("SELECT count(*) AS rows FROM favorite_recipes")["rows"] == 1
    owned = db_client.get("/favorite_recipes", headers=_auth(owner_token)).get_json()
    assert [recipe["id"] for recipe in owned] == [recipe_id]


def test_favourites_validate_the_recipe_id_and_the_pagination(db_client, register_user):
    """400 for a bad ``recipe_id`` or ``limit``/``offset``, 404 for an unknown recipe."""
    _, token = register_user()

    bad_payloads = [
        {},  # recipe_id is required
        {"recipe_id": 0},
        {"recipe_id": -1},
        {"recipe_id": "1"},
        {"recipe_id": 1.5},
        {"recipe_id": True},  # a boolean is not an id
        ["not-an-object"],
    ]
    for payload in bad_payloads:
        response = db_client.post("/favorite_recipes", json=payload, headers=_auth(token))
        assert response.status_code == 400, payload
        assert "error" in response.get_json(), payload

    # The recipe must exist: the foreign key would otherwise raise a database error.
    unknown = db_client.post("/favorite_recipes", json={"recipe_id": 424242}, headers=_auth(token))
    assert unknown.status_code == 404
    assert "424242" in unknown.get_json()["error"]

    # The list is paginated like the other collections (CONTRIBUTION.md §4).
    assert db_client.get("/favorite_recipes?limit=0", headers=_auth(token)).status_code == 400
    assert db_client.get("/favorite_recipes?offset=abc", headers=_auth(token)).status_code == 400
    assert db_client.get("/favorite_recipes?limit=200", headers=_auth(token)).status_code == 200
