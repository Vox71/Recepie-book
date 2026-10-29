"""System endpoints (``/``, ``/health``, ``/ready``) and the route table.

These are the first tests to run: they show that the application object itself
works, even when no database is available.
"""

from __future__ import annotations

# Every path and HTTP method the application must expose: all entries of
# openapi.yaml plus the two probes required by CONTRIBUTION.md §8.
EXPECTED_RULES = {
    "/": {"GET"},
    "/register": {"POST"},
    "/login": {"POST"},
    "/protected": {"GET"},
    "/user_preferences": {"POST"},
    "/recipes": {"GET", "POST"},
    "/recipes/<int:recipe_id>": {"GET", "PUT", "DELETE"},
    "/favorite_recipes": {"GET", "POST"},
    "/favorite_recipes/<int:recipe_id>": {"DELETE"},
    "/fridge_items": {"GET", "POST"},
    "/delete_expired_products": {"DELETE"},
    "/notify_expired": {"GET"},
    "/delete_expired": {"DELETE"},
    "/suggest_recipes": {"GET"},
    "/recommend_recipes": {"GET"},
    "/health": {"GET"},
    "/ready": {"GET"},
}


def test_index_returns_the_greeting(client):
    """``GET /`` answers with the text promised by openapi.yaml."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "Welcome to the recipe app!"


def test_health_is_ok_without_a_database(client):
    """``GET /health`` is a liveness probe: it must not touch the database."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_ready_reports_a_missing_database(client):
    """``GET /ready`` is a readiness probe: 503 means "do not send traffic yet"."""
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.get_json() == {"status": "not_ready", "database": "unavailable"}


def test_ready_reports_a_healthy_database(db_client):
    response = db_client.get("/ready")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ready", "database": "ok"}


def test_registered_routes_match_the_contract(app):
    """Guards the promise "22 addresses of openapi.yaml are implemented"."""
    routes: dict[str, set[str]] = {}
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        # GET and POST /recipes are two rules that share one path.
        routes.setdefault(str(rule), set()).update(rule.methods - {"HEAD", "OPTIONS"})
    assert routes == EXPECTED_RULES


def test_unknown_address_and_method_return_an_error_object(client):
    """Every failure is JSON ``{"error": "..."}`` (CONTRIBUTION.md §4)."""
    unknown = client.get("/no-such-endpoint")
    assert unknown.status_code == 404
    assert set(unknown.get_json()) == {"error"}

    wrong_method = client.delete("/login")
    assert wrong_method.status_code == 405
    assert set(wrong_method.get_json()) == {"error"}
