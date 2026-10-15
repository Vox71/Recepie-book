"""System endpoints (``/``, ``/health``, ``/ready``) and route registration."""

from __future__ import annotations

# The full contract implemented by the application (paths and methods of openapi.yaml
# plus the health probes required by CONTRIBUTION.md §8).
EXPECTED_RULES = {
    "/": {"GET"},
    "/register": {"POST"},
    "/login": {"POST"},
    "/protected": {"GET"},
    "/user_preferences": {"POST"},
    "/recipes": {"GET", "POST"},
    "/recipes/<int:recipe_id>": {"GET", "PUT", "DELETE"},
    "/fridge_items": {"GET", "POST"},
    "/delete_expired_products": {"DELETE"},
    "/notify_expired": {"GET"},
    "/delete_expired": {"DELETE"},
    "/suggest_recipes": {"GET"},
    "/recommend_recipes": {"GET"},
    "/health": {"GET"},
    "/ready": {"GET"},
}


def test_index_returns_the_documented_greeting(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert response.get_data(as_text=True) == "Welcome to the recipe app!"


def test_registered_routes_match_the_contract(app):
    rules: dict[str, set[str]] = {}
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        # Several view functions may share one path (e.g. GET and POST /recipes).
        rules.setdefault(str(rule), set()).update(rule.methods - {"HEAD", "OPTIONS"})
    assert rules == EXPECTED_RULES


def test_health_is_ok_without_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_ready_reports_missing_database(client):
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.get_json() == {"status": "not_ready", "database": "unavailable"}


def test_ready_reports_healthy_database(db_client):
    response = db_client.get("/ready")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ready", "database": "ok"}


def test_unknown_route_returns_error_object(client):
    response = client.get("/no-such-endpoint")
    assert response.status_code == 404
    assert set(response.get_json()) == {"error"}


def test_method_not_allowed_returns_error_object(client):
    response = client.delete("/login")
    assert response.status_code == 405
    assert set(response.get_json()) == {"error"}
