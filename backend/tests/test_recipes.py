"""Recipes: ``/recipes`` (list, create) and ``/recipes/{id}`` (read, update, delete).

The database columns are ``recipe_name`` and ``instruction`` (docs/db_scheme.png)
while the API keeps the names of openapi.yaml (``name``/``instructions``); the
serializers translate between the two.
"""

from __future__ import annotations

RECIPE = {
    "name": "Tomato pasta",
    "ingredients": "pasta, tomato, cheese, olive oil",
    "instructions": "Boil the pasta, mix with tomato and cheese.",
    "difficulty_level": "easy",
}
SOUP = {
    "name": "Spinach soup",
    "ingredients": "spinach, water, onion",
    "instructions": "Boil the spinach with the onion.",
    "difficulty_level": "easy",
}


def _create(client, payload: dict = RECIPE) -> dict:
    """Create a recipe through the API and return the stored JSON object."""
    response = client.post("/recipes", json=payload)
    assert response.status_code == 201, response.get_json()
    names = {recipe["name"]: recipe for recipe in client.get("/recipes").get_json()}
    return names[payload["name"]]


def test_create_recipe_stores_it_under_the_database_column_names(db_client, db):
    response = db_client.post("/recipes", json=RECIPE)
    assert response.status_code == 201
    assert "message" in response.get_json()

    row = db.fetch_one(
        "SELECT recipe_name, ingredients, instruction, difficulty_level FROM recipes"
    )
    assert row == {
        "recipe_name": RECIPE["name"],
        "ingredients": RECIPE["ingredients"],
        "instruction": RECIPE["instructions"],
        "difficulty_level": RECIPE["difficulty_level"],
    }


def test_create_recipe_validates_the_payload(db_client):
    """400 for a missing field, a wrong type or a value longer than the column."""
    bad_payloads = [
        {key: value for key, value in RECIPE.items() if key != missing}
        for missing in ("name", "ingredients", "instructions", "difficulty_level")
    ]
    bad_payloads += [
        {**RECIPE, "name": ["not", "a", "string"]},
        {**RECIPE, "name": "x" * 201},  # recipes.recipe_name is varchar(200)
        {**RECIPE, "instructions": "x" * 10001},  # MAX_TEXT_FIELD_LENGTH (text column)
        {**RECIPE, "difficulty_level": "x" * 51},  # varchar(50)
    ]
    for payload in bad_payloads:
        response = db_client.post("/recipes", json=payload)
        assert response.status_code == 400, payload
        assert "error" in response.get_json()

    # recipes.instruction is text, so an instruction longer than the old 100 characters
    # of the diagram is accepted (openapi.yaml declares maxLength 10000).
    long_instruction = {**RECIPE, "name": "Long recipe", "instructions": "x" * 5000}
    assert db_client.post("/recipes", json=long_instruction).status_code == 201


def test_list_recipes_returns_every_recipe(db_client):
    """openapi.yaml: ``POST /recipes`` is the only route without a token check."""
    assert db_client.post("/recipes", json=RECIPE).status_code == 201
    assert db_client.post("/recipes", json=SOUP).status_code == 201

    response = db_client.get("/recipes")
    assert response.status_code == 200
    recipes = response.get_json()
    assert {recipe["name"] for recipe in recipes} == {RECIPE["name"], SOUP["name"]}
    for recipe in recipes:
        assert isinstance(recipe["id"], int)
        # cuisine_type was removed from docs/db_scheme.png and from openapi.yaml.
        assert "cuisine_type" not in recipe


def test_list_recipes_returns_one_page(db_client):
    """``GET /recipes?limit=&offset=``: without the parameters the defaults apply."""
    payloads = [{**RECIPE, "name": f"Recipe {index}"} for index in range(5)]
    for payload in payloads:
        assert db_client.post("/recipes", json=payload).status_code == 201

    everything = db_client.get("/recipes").get_json()
    assert [recipe["name"] for recipe in everything] == [payload["name"] for payload in payloads]

    page = db_client.get("/recipes?limit=2&offset=1").get_json()
    assert [recipe["name"] for recipe in page] == ["Recipe 1", "Recipe 2"]

    tail = db_client.get("/recipes?offset=4").get_json()
    assert [recipe["name"] for recipe in tail] == ["Recipe 4"]
    assert db_client.get("/recipes?offset=10").get_json() == []


def test_list_recipes_validates_the_pagination(db_client):
    """A wrong limit/offset is a 400 with the usual error object, never a database error."""
    for query in (
        "limit=0",
        "limit=-1",
        "limit=abc",
        "limit=201",  # MAX_PAGE_LIMIT
        "offset=-1",
        "offset=abc",
        "offset=1000001",  # MAX_PAGE_OFFSET
    ):
        response = db_client.get(f"/recipes?{query}")
        assert response.status_code == 400, query
        assert "error" in response.get_json(), query

    assert db_client.get("/recipes?limit=200&offset=0").status_code == 200


def test_get_recipe_by_id(db_client):
    recipe = _create(db_client)

    response = db_client.get(f"/recipes/{recipe['id']}")
    assert response.status_code == 200
    assert response.get_json() == {"id": recipe["id"], **RECIPE}

    unknown = db_client.get("/recipes/424242")
    assert unknown.status_code == 404
    assert "424242" in unknown.get_json()["error"]


def test_update_recipe(db_client):
    recipe = _create(db_client)

    response = db_client.put(
        f"/recipes/{recipe['id']}",
        json={**RECIPE, "name": "Spicy pasta", "difficulty_level": "medium"},
    )
    assert response.status_code == 200
    assert "message" in response.get_json()

    stored = db_client.get(f"/recipes/{recipe['id']}").get_json()
    assert stored["name"] == "Spicy pasta"
    assert stored["difficulty_level"] == "medium"
    assert stored["ingredients"] == RECIPE["ingredients"]

    # The body is validated and an unknown id is a 404.
    assert db_client.put(f"/recipes/{recipe['id']}", json={"name": "only name"}).status_code == 400
    assert db_client.put("/recipes/424242", json=RECIPE).status_code == 404


def test_delete_recipe(db_client):
    recipe = _create(db_client)

    response = db_client.delete(f"/recipes/{recipe['id']}")
    assert response.status_code == 200
    assert "message" in response.get_json()

    assert db_client.get(f"/recipes/{recipe['id']}").status_code == 404
    assert db_client.get("/recipes").get_json() == []
    assert db_client.delete("/recipes/424242").status_code == 404
