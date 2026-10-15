"""Fridge contract tests: ``/fridge_items`` and ``/delete_expired_products``."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


@pytest.mark.parametrize(
    "payload",
    [
        {"user_id": 1},
        ["not-an-object"],
        [{}],
        [{"user_id": 1, "product_name": "milk", "expiration_date": "2026-01-01"}],
        [{"user_id": 1, "product_name": "milk", "expiration_date": "2026-01-01", "quantity": 0}],
        [{"user_id": 1, "product_name": "milk", "expiration_date": "01.01.2026", "quantity": 1}],
        [{"user_id": 0, "product_name": "milk", "expiration_date": "2026-01-01", "quantity": 1}],
        [{"user_id": 1, "product_name": "   ", "expiration_date": "2026-01-01", "quantity": 1}],
    ],
)
def test_add_items_rejects_invalid_payloads(db_client, payload):
    response = db_client.post("/fridge_items", json=payload)
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_add_items_requires_at_least_one_item(db_client):
    assert db_client.post("/fridge_items", json=[]).status_code == 400


def test_add_items_rejects_unknown_user(db_client):
    payload = [
        {
            "user_id": 999999,
            "product_name": "milk",
            "expiration_date": TOMORROW.isoformat(),
            "quantity": 1,
        }
    ]
    response = db_client.post("/fridge_items", json=payload)
    assert response.status_code == 400
    assert "999999" in response.get_json()["error"]


def test_add_and_list_items(db_client, register_user, add_fridge_items):
    user_id, _ = register_user()
    add_fridge_items(user_id, "milk", TOMORROW, quantity=2)

    response = db_client.get("/fridge_items")
    assert response.status_code == 200

    items = response.get_json()
    assert len(items) == 1
    item = items[0]
    assert isinstance(item["id"], int)
    assert item["user_id"] == user_id
    assert item["product_name"] == "milk"
    assert item["expiration_date"] == TOMORROW.isoformat()
    assert item["quantity"] == 2
    assert item["last_added"] is not None


def test_list_items_returns_items_of_every_user(db_client, register_user, add_fridge_items):
    """openapi.yaml: ``GET /fridge_items`` is not filtered by the token."""
    first, _ = register_user(email="first@example.com")
    second, _ = register_user(email="second@example.com")
    add_fridge_items(first, "milk", TOMORROW)
    add_fridge_items(second, "bread", TOMORROW)

    items = db_client.get("/fridge_items").get_json()
    assert {item["user_id"] for item in items} == {first, second}


def test_delete_expired_products_removes_only_expired_items(
    db_client, register_user, add_fridge_items
):
    user_id, _ = register_user()
    add_fridge_items(user_id, "old milk", YESTERDAY)
    add_fridge_items(user_id, "fresh bread", TOMORROW)
    add_fridge_items(user_id, "expires today", TODAY)

    response = db_client.delete("/delete_expired_products")
    assert response.status_code == 200
    assert "Deleted 1 expired product(s)" == response.get_json()["message"]

    remaining = {item["product_name"] for item in db_client.get("/fridge_items").get_json()}
    assert remaining == {"fresh bread", "expires today"}


def test_delete_expired_products_is_idempotent(db_client, register_user, add_fridge_items):
    """The broken date reference mentioned in openapi.yaml must not reappear."""
    user_id, _ = register_user()
    add_fridge_items(user_id, "old milk", YESTERDAY)

    assert db_client.delete("/delete_expired_products").status_code == 200
    second_run = db_client.delete("/delete_expired_products")
    assert second_run.status_code == 200
    assert second_run.get_json()["message"] == "Deleted 0 expired product(s)"
