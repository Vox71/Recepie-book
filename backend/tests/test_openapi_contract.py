"""Contract tests for ``openapi.yaml`` (CONTRIBUTION.md §4, sprint 2 tasks 5 and 7).

Three questions are answered here, and none of them relies on a second hand-written copy
of the contract:

* is the file itself a valid OpenAPI 3.0 document, so Swagger UI and any client
  generator can consume it?  Before these tests existed a ``servers`` block nested in
  ``info`` made the file invalid while every test stayed green;
* does it describe exactly the addresses and the pagination limits of the application?
  The route table is read from the file and compared with ``app.url_map``, so the list of
  addresses is no longer kept in two places by hand;
* do the real answers of the running application match the schemas of the file?
  ``openapi-schema-validator`` understands OpenAPI ``nullable``, so an imported recipe
  with ``null`` instructions and a ``date-time`` without an offset are checked too.

The dependencies (PyYAML, jsonschema, openapi-schema-validator, openapi-spec-validator)
are development-only: ``backend/requirements-dev.txt`` (CONTRIBUTION.md §11).
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import FormatChecker
from openapi_schema_validator import OAS30Validator
from openapi_spec_validator import validate
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4

from app.validation import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, MAX_PAGE_OFFSET

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "openapi.yaml"
# Namespace under which the parsed file is registered, so a schema can follow its $ref.
CONTRACT_URI = "urn:recipe-book:openapi"
HTTP_METHODS = {"get", "put", "post", "delete", "patch", "head", "options", "trace"}
# Every address of openapi.yaml that takes ?limit=&offset= (CONTRIBUTION.md §4).
PAGINATED_ROUTES = [("/recipes", "get"), ("/favorite_recipes", "get"), ("/fridge_items", "get")]
RECIPE_PAYLOAD = {
    "name": "Contract soup",
    "ingredients": "Картофель — 3 шт., Соль",
    "instructions": "Сварить.",
    "difficulty_level": "easy",
}


@lru_cache(maxsize=1)
def contract() -> dict:
    """Parsed ``openapi.yaml`` (read once per test session)."""
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@lru_cache(maxsize=1)
def _registry() -> Registry:
    """Resolution context that lets a schema reference ``#/components/...`` of the file."""
    document = Resource.from_contents(contract(), default_specification=DRAFT4)
    return Registry().with_resource(CONTRACT_URI, document)


def _absolute(node: Any) -> Any:
    """Rewrite local ``$ref`` pointers to absolute ones, so nested schemas resolve.

    A validator created for a fragment (say the schema of one response) resolves
    ``#/components/schemas/Recipe`` against that fragment, not against the whole file;
    prefixing every pointer with :data:`CONTRACT_URI` fixes the base.
    """
    if isinstance(node, dict):
        return {
            key: (
                f"{CONTRACT_URI}{value}"
                if key == "$ref" and isinstance(value, str) and value.startswith("#/")
                else _absolute(value)
            )
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_absolute(item) for item in node]
    return node


def _validator(schema: dict) -> OAS30Validator:
    """Validator of one schema of the contract (``nullable`` and formats are honoured)."""
    return OAS30Validator(_absolute(schema), registry=_registry(), format_checker=FormatChecker())


def normalize_path(path: str) -> str:
    """Erase the parameter name: ``/recipes/{id}`` and ``/recipes/<int:recipe_id>`` match."""
    return re.sub(r"{[^}]+}|<[^>]+>", "{}", path)


def operations() -> list[tuple[str, str, dict]]:
    """``(path, method, operation)`` for every HTTP method of every documented path."""
    return [
        (path, method, operation)
        for path, item in contract()["paths"].items()
        for method, operation in item.items()
        if method in HTTP_METHODS
    ]


def documented_schema(path: str, method: str, status: int) -> tuple[str, dict]:
    """Media type and schema documented for the answer ``status`` of ``method path``."""
    responses = contract()["paths"][path][method]["responses"]
    documented = sorted(int(code) for code in responses)
    assert (
        str(status) in responses
    ), f"{method.upper()} {path} answered {status}, but the contract documents {documented}"
    content = responses[str(status)]["content"]
    media_type = "text/plain" if "text/plain" in content else "application/json"
    return media_type, content[media_type]["schema"]


def assert_matches_contract(response, path: str, method: str) -> None:
    """Fail with the schema violations when an answer is not what the contract promises."""
    media_type, schema = documented_schema(path, method, response.status_code)
    instance = (
        response.get_data(as_text=True) if media_type == "text/plain" else response.get_json()
    )
    assert instance is not None, f"{method.upper()} {path} -> {response.status_code}: empty body"
    errors = [error.message for error in _validator(schema).iter_errors(instance)]
    assert (
        not errors
    ), f"{method.upper()} {path} -> {response.status_code} violates the contract: " + "; ".join(
        errors
    )


def test_the_contract_is_a_valid_openapi_document():
    """``validate`` accepts the file: a structural mistake breaks the tools silently."""
    document = contract()
    validate(document)  # raises OpenAPIValidationError on a structural mistake

    assert document["openapi"].startswith("3.0"), document["openapi"]
    assert {"title", "version"} <= set(document["info"])
    # ``servers`` belongs to the document root: nested in ``info`` the document is invalid
    # and Swagger UI has no address to call.
    assert "servers" not in document["info"]
    assert document["servers"], "the contract must declare at least one server"
    for server in document["servers"]:
        for variable in re.findall(r"{(\w+)}", server["url"]):
            assert variable in server.get(
                "variables", {}
            ), f"server variable '{variable}' is used in {server['url']} but not declared"


def test_every_operation_documents_a_success_answer():
    """No address is described without the answer it normally returns."""
    for path, method, operation in operations():
        statuses = {int(code) for code in operation["responses"]}
        assert any(
            200 <= status < 300 for status in statuses
        ), f"{method.upper()} {path} documents no 2xx answer: {sorted(statuses)}"


def test_every_token_protected_operation_documents_401():
    """A route behind ``security`` must describe its authentication failure."""
    protected = 0
    for path, method, operation in operations():
        if not operation.get("security"):
            continue
        protected += 1
        statuses = {int(code) for code in operation["responses"]}
        assert 401 in statuses, f"{method.upper()} {path} needs a token, so 401 must be documented"
    assert protected, "no operation declares security: the check would be vacuous"


def test_the_contract_describes_exactly_the_routes_of_the_application(app):
    """Every documented address exists and every implemented address is documented.

    This replaces a hand-written copy of the route table: adding an address to the file
    without implementing it (or the other way round) now fails here instead of surviving
    until the next review.
    """
    documented = {(normalize_path(path), method.upper()) for path, method, _ in operations()}
    implemented: set[tuple[str, str]] = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            # Flask's own file server, no address in the contract (CONTRIBUTION.md §16).
            continue
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            implemented.add((normalize_path(str(rule)), method))

    undocumented = sorted(implemented - documented)
    missing = sorted(documented - implemented)
    assert not undocumented, f"implemented but undocumented: {undocumented}"
    assert not missing, f"documented but not implemented: {missing}"


def test_the_pagination_limits_match_the_application_constants():
    """The numbers in the file are the constants ``app/validation.py`` validates with."""
    for path, method in PAGINATED_ROUTES:
        parameters = {
            parameter["name"]: parameter["schema"]
            for parameter in contract()["paths"][path][method].get("parameters", [])
            if parameter["in"] == "query"
        }
        assert set(parameters) == {"limit", "offset"}, f"{method.upper()} {path}: {parameters}"
        assert parameters["limit"] == {
            "type": "integer",
            "minimum": 1,
            "maximum": MAX_PAGE_LIMIT,
            "default": DEFAULT_PAGE_LIMIT,
        }, f"{method.upper()} {path}: limit"
        assert parameters["offset"] == {
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_PAGE_OFFSET,
            "default": 0,
        }, f"{method.upper()} {path}: offset"


@pytest.mark.parametrize(
    ("method", "path", "kwargs", "status"),
    [
        ("get", "/protected", {}, 401),
        ("get", "/favorite_recipes", {}, 401),
        ("get", "/notify_expired", {}, 401),
        ("get", "/recipes", {"query_string": {"limit": 0}}, 400),
        ("get", "/fridge_items", {"query_string": {"offset": "abc"}}, 400),
        ("post", "/register", {"json": {"username": "contract"}}, 400),
        ("post", "/login", {"json": {}}, 400),
        ("post", "/recipes", {"json": "not an object"}, 400),
    ],
)
def test_failure_answers_match_the_error_schema(client, method, path, kwargs, status):
    """Every failure has the documented status and the documented ``{"error": ...}`` body."""
    response = client.open(path, method=method.upper(), **kwargs)

    assert response.status_code == status, response.get_json()
    assert_matches_contract(response, path, method)


def test_the_system_answers_match_the_contract(client):
    """``/`` (plain text), ``/health`` and ``/ready`` answer exactly what is documented."""
    assert_matches_contract(client.get("/"), "/", "get")
    assert_matches_contract(client.get("/health"), "/health", "get")
    # This application has no database, so the readiness probe answers the documented 503.
    assert_matches_contract(client.get("/ready"), "/ready", "get")


def test_authentication_and_recipe_answers_match_the_contract(db_client):
    """Registration, login, the protected probe and the recipe CRUD of the contract."""
    register = db_client.post(
        "/register",
        json={"username": "contract", "email": "contract@example.com", "password": "sup3r-secret"},
    )
    assert_matches_contract(register, "/register", "post")

    login = db_client.post(
        "/login", json={"email": "contract@example.com", "password": "sup3r-secret"}
    )
    assert_matches_contract(login, "/login", "post")
    headers = {"Authorization": f"Bearer {login.get_json()['token']}"}
    assert_matches_contract(db_client.get("/protected", headers=headers), "/protected", "get")

    assert_matches_contract(db_client.post("/recipes", json=RECIPE_PAYLOAD), "/recipes", "post")
    page = db_client.get("/recipes", query_string={"limit": 1})
    assert_matches_contract(page, "/recipes", "get")
    recipe_id = page.get_json()[0]["id"]

    assert_matches_contract(db_client.get(f"/recipes/{recipe_id}"), "/recipes/{id}", "get")
    updated = db_client.put(f"/recipes/{recipe_id}", json={**RECIPE_PAYLOAD, "name": "Renamed"})
    assert_matches_contract(updated, "/recipes/{id}", "put")
    assert_matches_contract(db_client.delete(f"/recipes/{recipe_id}"), "/recipes/{id}", "delete")
    # The documented 404 of the same address, once the recipe is gone.
    assert_matches_contract(db_client.delete(f"/recipes/{recipe_id}"), "/recipes/{id}", "delete")


def test_favorites_fridge_and_notification_answers_match_the_contract(
    db_client, register_user, add_relative_fridge_items
):
    """The remaining addresses of the contract: favourites, fridge, notifications, ML."""
    user_id, token = register_user(email="contract@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    db_client.post("/recipes", json=RECIPE_PAYLOAD)
    recipe_id = db_client.get("/recipes").get_json()[0]["id"]

    favourite = db_client.post("/favorite_recipes", json={"recipe_id": recipe_id}, headers=headers)
    assert_matches_contract(favourite, "/favorite_recipes", "post")
    favourites = db_client.get("/favorite_recipes", headers=headers)
    assert_matches_contract(favourites, "/favorite_recipes", "get")
    removed = db_client.delete(f"/favorite_recipes/{recipe_id}", headers=headers)
    assert_matches_contract(removed, "/favorite_recipes/{id}", "delete")

    # An expired product for the notifications and the recommendations.  The date is
    # relative to the database clock, so the answer does not depend on the test process.
    add_relative_fridge_items(user_id, "Молоко", -3)
    assert_matches_contract(db_client.get("/fridge_items"), "/fridge_items", "get")

    extra = [
        {
            "user_id": user_id,
            "product_name": "Соль",
            "expiration_date": (date.today() + timedelta(days=30)).isoformat(),
            "quantity": 1,
        }
    ]
    assert_matches_contract(db_client.post("/fridge_items", json=extra), "/fridge_items", "post")

    notified = db_client.get("/notify_expired", headers=headers)
    assert_matches_contract(notified, "/notify_expired", "get")
    assert_matches_contract(
        db_client.get("/suggest_recipes", headers=headers), "/suggest_recipes", "get"
    )
    recommended = db_client.get("/recommend_recipes", headers=headers)
    assert_matches_contract(recommended, "/recommend_recipes", "get")

    preferences = {"user_id": user_id, "allergies": ["молоко"], "preferences": ["суп"]}
    saved = db_client.post("/user_preferences", json=preferences)
    assert_matches_contract(saved, "/user_preferences", "post")

    assert_matches_contract(
        db_client.delete("/delete_expired", headers=headers), "/delete_expired", "delete"
    )
    deleted = db_client.delete("/delete_expired_products")
    assert_matches_contract(deleted, "/delete_expired_products", "delete")


def test_an_imported_recipe_matches_the_contract(db_client, db):
    """A recipe written by the importer is a valid ``Recipe``: nulls and ``ingredient_list``.

    This is the schema part of task 5: three fields are ``nullable`` and the structured
    ingredients arrive in ``sort_order`` with an optional quantity.
    """
    source = "https://www.povarenok.ru/recipes/show/4242/"
    db.execute(
        "INSERT INTO recipes (source_url, recipe_name, ingredients) VALUES (%s, %s, %s)",
        (source, "Уха", "Лосось — 400 г, Соль"),
    )
    recipe_id = int(db.fetch_one("SELECT id FROM recipes WHERE source_url = %s", (source,))["id"])
    db.execute(
        """
        INSERT INTO recipe_ingredients (recipe_id, ingredient_name, quantity_text, sort_order)
        VALUES (%s, %s, %s, %s), (%s, %s, NULL, %s)
        """,
        (recipe_id, "Лосось", "400 г", 0, recipe_id, "Соль", 1),
    )

    assert_matches_contract(db_client.get("/recipes"), "/recipes", "get")
    assert_matches_contract(db_client.get(f"/recipes/{recipe_id}"), "/recipes/{id}", "get")
