"""``/user_preferences``: allergies and preferences of a user.

openapi.yaml documents that this route is not protected by a token and takes
``user_id`` from the body, so the tests pin that (unsafe) behaviour.
"""

from __future__ import annotations


def test_preferences_are_stored_normalized_and_cleared(db_client, register_user, db):
    user_id, _ = register_user()
    response = db_client.post(
        "/user_preferences",
        json={"user_id": user_id, "allergies": ["peanuts", "milk"], "preferences": ["vegan"]},
    )
    assert response.status_code == 200
    assert "message" in response.get_json()

    # users.allergies / users.preferences keep the text view of the lists ...
    stored = db.fetch_one("SELECT allergies, preferences FROM users WHERE id = %s", (user_id,))
    assert stored["allergies"] == "peanuts, milk"
    assert stored["preferences"] == "vegan"
    # ... while user_allergy_preferences keeps one row per allergy.
    rows = db.fetch_all(
        "SELECT allergy_name FROM user_allergy_preferences WHERE user_id = %s ORDER BY id",
        (user_id,),
    )
    assert [row["allergy_name"] for row in rows] == ["peanuts", "milk"]

    # A second call replaces the old values instead of adding new ones.
    assert (
        db_client.post(
            "/user_preferences", json={"user_id": user_id, "allergies": ["soy"]}
        ).status_code
        == 200
    )
    rows = db.fetch_all(
        "SELECT allergy_name FROM user_allergy_preferences WHERE user_id = %s ORDER BY id",
        (user_id,),
    )
    assert [row["allergy_name"] for row in rows] == ["soy"]

    # An empty list clears both the text column and the normalized rows.
    assert (
        db_client.post("/user_preferences", json={"user_id": user_id, "allergies": []}).status_code
        == 200
    )
    stored = db.fetch_one("SELECT allergies FROM users WHERE id = %s", (user_id,))
    assert stored["allergies"] is None
    assert (
        db.fetch_all("SELECT id FROM user_allergy_preferences WHERE user_id = %s", (user_id,)) == []
    )

    # user_id is validated against the users table.
    unknown = db_client.post("/user_preferences", json={"user_id": 999999, "allergies": []})
    assert unknown.status_code == 400
    assert "999999" in unknown.get_json()["error"]


def test_user_preferences_validation(client):
    """Validation runs before any database access, so a bad body is 400, not 401."""
    bad_payloads = [
        {},  # user_id is required
        {"user_id": "1"},  # user_id must be an integer
        {"user_id": 0, "allergies": []},  # user_id must be positive
        {"user_id": 1, "allergies": "nuts"},  # allergies must be an array
        {"user_id": 1, "allergies": ["nuts", 42]},  # ... of strings only
        {"user_id": 1, "preferences": ["vegan", "   "]},  # no empty terms
    ]
    for payload in bad_payloads:
        response = client.post("/user_preferences", json=payload)
        assert response.status_code == 400, payload
        assert "error" in response.get_json()
