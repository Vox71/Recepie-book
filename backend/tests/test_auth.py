"""Authentication contract tests: ``/register``, ``/login``, ``/protected``."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

VALID_PAYLOAD = {
    "username": "tester",
    "email": "tester@example.com",
    "password": "sup3r-secret-password",
}


def _token(secret: str, *, subject: str | None = "1", expires_in: int = 3600) -> str:
    payload = {"exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in)}
    if subject is not None:
        payload["sub"] = subject
    return jwt.encode(payload, secret, algorithm="HS256")


def test_register_requires_a_json_object(client):
    response = client.post("/register", data="not-json", content_type="application/json")
    assert response.status_code == 400
    assert "error" in response.get_json()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"username": "tester", "email": "tester@example.com"},
        {"username": "tester", "email": "not-an-email", "password": "sup3r-secret-password"},
        {"username": "tester", "email": "tester@example.com", "password": "short"},
        {"username": "   ", "email": "tester@example.com", "password": "sup3r-secret-password"},
        {
            "username": "tester",
            "email": "tester@example.com",
            "password": "sup3r-secret-password",
            "allergies": 42,
        },
    ],
)
def test_register_rejects_invalid_payloads(client, payload):
    response = client.post("/register", json=payload)
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_register_creates_a_user(db_client):
    response = db_client.post("/register", json=VALID_PAYLOAD)
    assert response.status_code == 201
    body = response.get_json()
    assert isinstance(body["user_id"], int)
    assert body["message"]


def test_register_accepts_string_and_list_terms(db_client):
    """openapi.yaml: allergies/preferences are forwarded to the database unchanged."""
    payload = {**VALID_PAYLOAD, "allergies": "nuts", "preferences": ["grill", "vegan"]}
    assert db_client.post("/register", json=payload).status_code == 201


def test_register_rejects_duplicate_email(db_client):
    assert db_client.post("/register", json=VALID_PAYLOAD).status_code == 201
    duplicate = db_client.post("/register", json={**VALID_PAYLOAD, "username": "another"})
    assert duplicate.status_code == 400
    assert "email" in duplicate.get_json()["error"].lower()


def test_register_rejects_duplicate_username(db_client):
    assert db_client.post("/register", json=VALID_PAYLOAD).status_code == 201
    duplicate = db_client.post("/register", json={**VALID_PAYLOAD, "email": "another@example.com"})
    assert duplicate.status_code == 400
    assert "username" in duplicate.get_json()["error"].lower()


def test_login_requires_email_and_password(client):
    assert client.post("/login", json={}).status_code == 400
    assert client.post("/login", json={"email": "tester@example.com"}).status_code == 400


def test_login_returns_token(db_client):
    db_client.post("/register", json=VALID_PAYLOAD)
    response = db_client.post(
        "/login", json={"email": VALID_PAYLOAD["email"], "password": VALID_PAYLOAD["password"]}
    )
    assert response.status_code == 200
    assert response.get_json()["token"]


def test_login_rejects_unknown_user(db_client):
    response = db_client.post(
        "/login", json={"email": "ghost@example.com", "password": "sup3r-secret-password"}
    )
    assert response.status_code == 401
    assert "error" in response.get_json()


def test_login_rejects_wrong_password(db_client):
    db_client.post("/register", json=VALID_PAYLOAD)
    response = db_client.post(
        "/login", json={"email": VALID_PAYLOAD["email"], "password": "wrong-password"}
    )
    assert response.status_code == 401


def test_protected_requires_a_bearer_token(client):
    assert client.get("/protected").status_code == 401
    assert client.get("/protected", headers={"Authorization": "Token abc"}).status_code == 401
    assert client.get("/protected", headers={"Authorization": "Bearer "}).status_code == 401


def test_protected_rejects_a_malformed_token(client):
    response = client.get("/protected", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_protected_rejects_an_expired_token(client, jwt_secret):
    token = _token(jwt_secret, expires_in=-3600)
    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_protected_rejects_a_token_without_subject(client, jwt_secret):
    token = _token(jwt_secret, subject=None)
    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_protected_accepts_a_valid_token(client, jwt_secret):
    token = _token(jwt_secret, subject="5")
    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    # openapi.yaml declares user_id as a string for this endpoint.
    assert response.get_json() == {"message": "Access granted", "user_id": "5"}
