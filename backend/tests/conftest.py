"""Shared pytest fixtures (CONTRIBUTION.md §10).

Tests that need PostgreSQL are skipped automatically when ``TEST_DATABASE_URL``
(or ``DATABASE_URL``) is missing or unreachable, so contract level tests
(validation, authentication, probes) always run.
"""

from __future__ import annotations

import os

import psycopg2
import pytest
from flask import Flask

from app import create_app
from app.config import Settings

TEST_JWT_SECRET = "test-jwt-secret-not-for-production-use"
DEFAULT_PASSWORD = "sup3r-secret-password"
TRUNCATE_STATEMENT = (
    "TRUNCATE users, recipes, fridge_items, favorite_recipes, generated_recipes, "
    "user_allergy_preferences, fridge_item_versions, fridge_item_audit RESTART IDENTITY CASCADE"
)


def database_url_from_env() -> str:
    """Return the DSN used by the database-backed tests."""
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL", "")


def database_reachable(dsn: str) -> bool:
    """True when a connection to ``dsn`` can be established."""
    try:
        connection = psycopg2.connect(dsn, connect_timeout=3)
    except (psycopg2.Error, OSError, ValueError):
        return False
    connection.close()
    return True


@pytest.fixture(scope="session")
def database_url() -> str:
    """DSN of a reachable PostgreSQL instance or a skip marker."""
    dsn = database_url_from_env()
    if not dsn:
        pytest.skip("TEST_DATABASE_URL/DATABASE_URL is not set")
    if not database_reachable(dsn):
        pytest.skip("PostgreSQL is not reachable")
    return dsn


@pytest.fixture()
def app():
    """Application without a database (validation and authentication code paths)."""
    settings = Settings({"JWT_SECRET": TEST_JWT_SECRET, "AUTO_INIT_SCHEMA": "false"})
    return create_app(settings)


@pytest.fixture()
def client(app):
    """HTTP client for the database-less application."""
    return app.test_client()


@pytest.fixture()
def db_app_factory(database_url):
    """Build database-backed applications, optionally with extra environment variables.

    ``db_app_factory(SMART_RECOMMENDATIONS_ENABLED="true")`` returns a second application
    that shares the same database but runs with the stub ML module switched on - that is
    how the feature flag is tested (app/config.py).
    """
    applications: list[Flask] = []

    def _build(**extra_env: str) -> Flask:
        settings = Settings(
            {
                "JWT_SECRET": TEST_JWT_SECRET,
                "DATABASE_URL": database_url,
                "AUTO_INIT_SCHEMA": "true",
                **extra_env,
            }
        )
        application = create_app(settings)
        with application.extensions["db"].cursor() as cur:
            cur.execute(TRUNCATE_STATEMENT)
        applications.append(application)
        return application

    try:
        yield _build
    finally:
        for application in applications:
            application.extensions["db"].reset_pool()


@pytest.fixture()
def db_app(db_app_factory):
    """Application bound to a real database with empty tables."""
    return db_app_factory()


@pytest.fixture()
def db_client(db_app):
    """HTTP client for the database-backed application."""
    return db_app.test_client()


@pytest.fixture()
def db(db_app):
    """Database facade of the database-backed application (for SQL assertions)."""
    return db_app.extensions["db"]


@pytest.fixture()
def jwt_secret() -> str:
    """Secret used to sign tokens in tests."""
    return TEST_JWT_SECRET


@pytest.fixture()
def register_user(db_client):
    """Register and log in a user, returning ``(user_id, token)``."""

    def _register(
        username: str | None = None,
        email: str = "tester@example.com",
        password: str = DEFAULT_PASSWORD,
        **extra,
    ) -> tuple[int, str]:
        # The default username is derived from the e-mail so that tests can
        # register several users without violating the unique username constraint.
        payload = {
            "username": username or email.split("@")[0],
            "email": email,
            "password": password,
            **extra,
        }
        response = db_client.post("/register", json=payload)
        assert response.status_code == 201, response.get_json()
        login = db_client.post("/login", json={"email": email, "password": password})
        assert login.status_code == 200, login.get_json()
        return response.get_json()["user_id"], login.get_json()["token"]

    return _register


@pytest.fixture()
def add_fridge_items(db_client):
    """Insert one fridge item for a user through the API."""

    def _add(user_id: int, product_name: str, expiration_date, quantity: int = 1) -> dict:
        item = {
            "user_id": user_id,
            "product_name": product_name,
            "expiration_date": expiration_date.isoformat(),
            "quantity": quantity,
        }
        response = db_client.post("/fridge_items", json=[item])
        assert response.status_code == 201, response.get_json()
        return item

    return _add
