"""Authentication: ``/register``, ``/login`` and ``/protected``.

Each endpoint has two tests: the happy path and the rejected input.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

VALID_USER = {
    "username": "tester",
    "email": "tester@example.com",
    "password": "sup3r-secret-password",
}
# Payloads that must be answered with 400. The limits mirror the column types of
# app/schema.sql, so oversized or missing input never reaches the database.
INVALID_USERS = [
    {},  # everything is missing
    {"username": "tester", "email": "tester@example.com"},  # password is missing
    {"username": "tester", "email": "not-an-email", "password": "sup3r-secret-password"},
    {"username": "tester", "email": "tester@example.com", "password": "short"},
    {"username": "   ", "email": "tester@example.com", "password": "sup3r-secret-password"},
    {"username": "t" * 81, "email": "tester@example.com", "password": "sup3r-secret-password"},
    {
        "username": "tester",
        "email": f"{'e' * 121}@example.com",
        "password": "sup3r-secret-password",
    },
    {
        "username": "tester",
        "email": "tester@example.com",
        "password": "sup3r-secret-password",
        "allergies": 42,
    },
    {
        "username": "tester",
        "email": "tester@example.com",
        "password": "sup3r-secret-password",
        "allergies": ["n" * 101],
    },
]


def _token(secret: str, *, subject: str | None = "1", expires_in: int = 3600) -> str:
    """Build a JWT by hand to test the checks of ``/protected``."""
    payload = {"exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in)}
    if subject is not None:
        payload["sub"] = subject
    return jwt.encode(payload, secret, algorithm="HS256")


def test_register_creates_a_user(db_client, db):
    """The password is hashed, the terms are stored and duplicates are refused."""
    payload = {**VALID_USER, "allergies": "nuts", "preferences": ["grill", "vegan"]}
    response = db_client.post("/register", json=payload)
    assert response.status_code == 201
    assert isinstance(response.get_json()["user_id"], int)

    # users.password keeps a scrypt hash (162 characters), never the typed password.
    stored = db.fetch_one("SELECT password, allergies, preferences FROM users")
    assert stored["password"] != VALID_USER["password"]
    assert stored["password"].startswith("scrypt:")
    assert len(stored["password"]) <= 200
    # Lists are stored as comma separated text plus one row per allergy.
    assert stored["allergies"] == "nuts"
    assert stored["preferences"] == "grill, vegan"
    rows = db.fetch_all("SELECT allergy_name FROM user_allergy_preferences ORDER BY id")
    assert [row["allergy_name"] for row in rows] == ["nuts"]

    # users.email (case-insensitive) and users.username are unique.
    duplicate_email = db_client.post("/register", json={**VALID_USER, "username": "other"})
    assert duplicate_email.status_code == 400
    assert "email" in duplicate_email.get_json()["error"].lower()

    duplicate_username = db_client.post("/register", json={**VALID_USER, "email": "other@x.com"})
    assert duplicate_username.status_code == 400
    assert "username" in duplicate_username.get_json()["error"].lower()


def test_register_rejects_invalid_payloads(client):
    for payload in INVALID_USERS:
        response = client.post("/register", json=payload)
        assert response.status_code == 400, payload
        assert "error" in response.get_json()

    not_json = client.post("/register", data="not-json", content_type="application/json")
    assert not_json.status_code == 400


def test_login_returns_a_token(db_client):
    """Wrong credentials are 401, the right ones give a token."""
    assert db_client.post("/register", json=VALID_USER).status_code == 201

    wrong_password = db_client.post(
        "/login", json={"email": VALID_USER["email"], "password": "wrong-password"}
    )
    assert wrong_password.status_code == 401

    unknown_user = db_client.post(
        "/login", json={"email": "ghost@example.com", "password": VALID_USER["password"]}
    )
    assert unknown_user.status_code == 401

    response = db_client.post(
        "/login", json={"email": VALID_USER["email"], "password": VALID_USER["password"]}
    )
    assert response.status_code == 200
    assert response.get_json()["token"]


def test_login_requires_email_and_password(client):
    assert client.post("/login", json={}).status_code == 400
    assert client.post("/login", json={"email": VALID_USER["email"]}).status_code == 400


def test_protected_accepts_a_valid_token(client, jwt_secret):
    token = _token(jwt_secret, subject="5")
    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    # openapi.yaml declares user_id as a string for this endpoint.
    assert response.get_json() == {"message": "Access granted", "user_id": "5"}


def test_protected_rejects_bad_tokens(client, jwt_secret):
    bad_headers = [
        {},  # no Authorization header at all
        {"Authorization": "Token abc"},  # wrong scheme instead of "Bearer"
        {"Authorization": "Bearer "},  # empty token
        {"Authorization": "Bearer not-a-jwt"},  # not a JWT at all
        {"Authorization": f"Bearer {_token(jwt_secret, expires_in=-3600)}"},  # expired
        {"Authorization": f"Bearer {_token(jwt_secret, subject=None)}"},  # no subject
    ]
    for headers in bad_headers:
        response = client.get("/protected", headers=headers)
        assert response.status_code == 401, headers
        assert "error" in response.get_json()
