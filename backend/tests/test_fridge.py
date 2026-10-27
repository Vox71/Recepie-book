"""Fridge: ``/fridge_items`` (list, add a batch) and ``/delete_expired_products``.

Both routes work with all users exactly as documented in openapi.yaml; the only
rules enforced here are input validation, SQL parameterisation and the shared
"expired" predicate of ``app/models/fridge.py`` (``expiration_date < CURRENT_DATE``).
"""

from __future__ import annotations

from datetime import date, timedelta

TOMORROW = date.today() + timedelta(days=1)


def test_add_and_list_fridge_items(db_client, register_user, db):
    user_id, _ = register_user()
    payload = [
        {
            "user_id": user_id,
            "product_name": "milk",
            "expiration_date": TOMORROW.isoformat(),
            "quantity": 2,
        }
    ]
    response = db_client.post("/fridge_items", json=payload)
    assert response.status_code == 201
    assert response.get_json() == {"message": "1 fridge item(s) added"}

    items = db_client.get("/fridge_items").get_json()
    assert len(items) == 1
    item = items[0]
    assert item["user_id"] == user_id
    assert item["product_name"] == "milk"
    assert item["expiration_date"] == TOMORROW.isoformat()
    # The API reports "id" while the column is fridge_items.item_id.
    assert isinstance(item["id"], int)
    assert isinstance(item["quantity"], int)
    assert item["quantity"] == 2
    assert item["last_added"] is not None

    row = db.fetch_one("SELECT item_id, quantity FROM fridge_items")
    assert item["id"] == row["item_id"]
    assert item["quantity"] == row["quantity"] == 2


def test_add_fridge_items_validates_the_payload(db_client, register_user):
    """The body is an array; every problem must be a 400, never a database error."""
    user_id, _ = register_user()
    valid_item = {
        "user_id": user_id,
        "product_name": "milk",
        "expiration_date": TOMORROW.isoformat(),
        "quantity": 1,
    }
    bad_payloads = [
        {"user_id": user_id},  # not an array
        [],  # empty array
        ["not-an-object"],
        [{}],
        [{key: value for key, value in valid_item.items() if key != "quantity"}],
        [{**valid_item, "quantity": 0}],  # fridge_items.quantity has CHECK (quantity > 0)
        [{**valid_item, "quantity": 1.5}],  # quantity is an integer
        [{**valid_item, "product_name": "m" * 101}],  # varchar(100)
        [{**valid_item, "expiration_date": "01.01.2026"}],  # ISO 8601 is required
        [{**valid_item, "user_id": 999999}],  # the user must exist (foreign key)
    ]
    for payload in bad_payloads:
        response = db_client.post("/fridge_items", json=payload)
        assert response.status_code == 400, payload
        assert "error" in response.get_json()


def test_delete_expired_products_removes_only_expired_items(
    db_client, register_user, add_fridge_items, db
):
    """The rule is ``expiration_date < CURRENT_DATE``: "today" is still a valid product."""
    today = db.fetch_one("SELECT CURRENT_DATE AS day")["day"]
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    user_id, _ = register_user()
    add_fridge_items(user_id, "old milk", yesterday)
    add_fridge_items(user_id, "fresh bread", tomorrow)
    add_fridge_items(user_id, "expires today", today)

    response = db_client.delete("/delete_expired_products")
    assert response.status_code == 200
    assert response.get_json() == {"message": "Deleted 1 expired product(s)"}

    # A product that expires today is still usable, so it stays in the fridge.
    remaining = {item["product_name"] for item in db_client.get("/fridge_items").get_json()}
    assert remaining == {"fresh bread", "expires today"}

    # Running it again deletes nothing instead of failing.
    again = db_client.delete("/delete_expired_products")
    assert again.status_code == 200
    assert again.get_json() == {"message": "Deleted 0 expired product(s)"}


def test_delete_expired_products_uses_the_database_date_as_the_boundary(
    db_client, register_user, add_relative_fridge_items, db
):
    """Yesterday is expired, today is still valid, tomorrow is valid; a repeat deletes 0."""
    user_id, _ = register_user()
    add_relative_fridge_items(user_id, "two days ago", -2)
    add_relative_fridge_items(user_id, "expired yesterday", -1)
    add_relative_fridge_items(user_id, "expires today", 0)
    add_relative_fridge_items(user_id, "expires tomorrow", 1)

    response = db_client.delete("/delete_expired_products")
    assert response.status_code == 200
    assert response.get_json() == {"message": "Deleted 2 expired product(s)"}

    # A product that expires today is still usable, so it stays in the fridge.
    remaining = {
        item["product_name"]: item["expiration_date"]
        for item in db_client.get("/fridge_items").get_json()
    }
    assert set(remaining) == {"expires today", "expires tomorrow"}
    today = db.fetch_one("SELECT CURRENT_DATE AS day")["day"].isoformat()
    assert remaining["expires today"] == today

    # Running it again deletes nothing instead of failing.
    again = db_client.delete("/delete_expired_products")
    assert again.status_code == 200
    assert again.get_json() == {"message": "Deleted 0 expired product(s)"}
