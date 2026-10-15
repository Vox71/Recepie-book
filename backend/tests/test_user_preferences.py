"""``/user_preferences`` contract tests.

openapi.yaml documents that this route is not protected by a token and takes
``user_id`` from the body, therefore these tests pin that (unsafe) behaviour.
"""

from __future__ import annotations

import pytest


def test_preferences_do_not_require_a_token(client):
    """Input validation runs before any database access, so 400 (not 401) is expected."""
    response = client.post("/user_preferences", json={})
    assert response.status_code == 400
    assert "error" in response.get_json()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"user_id": "1"},
        {"user_id": 0, "allergies": []},
        {"user_id": 1, "allergies": "nuts"},
        {"user_id": 1, "allergies": ["nuts", 42]},
        {"user_id": 1, "preferences": ["vegan", "   "]},
    ],
)
def test_preferences_validation(client, payload):
    response = client.post("/user_preferences", json=payload)
    assert response.status_code == 400


def test_preferences_are_persisted(db_client, register_user):
    user_id, _ = register_user()
    response = db_client.post(
        "/user_preferences",
        json={"user_id": user_id, "allergies": ["peanuts"], "preferences": ["vegan"]},
    )
    assert response.status_code == 200
    assert "message" in response.get_json()

    row = db_client.application.extensions["db"].fetch_one(
        "SELECT allergies, preferences FROM users WHERE id = %s", (user_id,)
    )
    assert row["allergies"] == ["peanuts"]
    assert row["preferences"] == ["vegan"]


def test_preferences_for_unknown_user_are_rejected(db_client):
    response = db_client.post("/user_preferences", json={"user_id": 999999, "allergies": []})
    assert response.status_code == 400
    assert "999999" in response.get_json()["error"]
