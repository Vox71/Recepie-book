"""Fridge: ``/fridge_items`` (list, add a batch) and ``/delete_expired_products``.

Both routes work with all users exactly as documented in openapi.yaml; the only
rules enforced here are input validation, SQL parameterisation and the shared
"expired" predicate of ``app/models/fridge.py`` (``expiration_date < CURRENT_DATE``).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.serializers import iso_date, iso_datetime, serialize_fridge_item

TOMORROW = date.today() + timedelta(days=1)


def test_serializers_render_missing_values_and_keep_the_utc_offset():
    """``FridgeItem`` fields: ``null`` stays ``null``, a naked timestamp becomes RFC 3339.

    ``fridge_items.last_added`` is a ``timestamp`` without a time zone, while
    ``openapi.yaml`` declares ``format: date-time``: the serializer adds the UTC offset,
    otherwise a strict client validator rejects the answer (checked by
    ``test_openapi_contract.py``).
    """
    item = serialize_fridge_item(
        {
            "item_id": 1,
            "user_id": 2,
            "product_name": "Молоко",
            "expiration_date": None,
            "quantity": None,
            "last_added": datetime(2026, 11, 12, 10, 30),
        }
    )

    assert item["expiration_date"] is None
    assert item["quantity"] is None
    assert item["last_added"] == "2026-11-12T10:30:00+00:00"
    assert iso_date(None) is None
    assert iso_datetime(None) is None


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


def test_list_fridge_items_returns_one_page(db_client, register_user, add_fridge_items):
    """``GET /fridge_items?limit=&offset=``: the defaults return the whole (small) list."""
    user_id, _ = register_user()
    names = ["milk", "bread", "cheese"]
    for offset, name in enumerate(names):
        add_fridge_items(user_id, name, TOMORROW + timedelta(days=offset))

    everything = db_client.get("/fridge_items").get_json()
    assert [item["product_name"] for item in everything] == names

    page = db_client.get("/fridge_items?limit=1&offset=1").get_json()
    assert [item["product_name"] for item in page] == ["bread"]

    tail = db_client.get("/fridge_items?offset=2").get_json()
    assert [item["product_name"] for item in tail] == ["cheese"]
    assert db_client.get("/fridge_items?offset=3").get_json() == []


def test_list_fridge_items_validates_the_pagination(db_client):
    """A wrong limit/offset is a 400 with the usual error object, never a database error."""
    for query in (
        "limit=0",
        "limit=-1",
        "limit=abc",
        "limit=201",  # MAX_PAGE_LIMIT
        "offset=-1",
        "offset=abc",
        "offset=1000001",  # MAX_PAGE_OFFSET
    ):
        response = db_client.get(f"/fridge_items?{query}")
        assert response.status_code == 400, query
        assert "error" in response.get_json(), query

    assert db_client.get("/fridge_items?limit=200&offset=0").status_code == 200


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


def test_profile_fridge_is_scoped_to_the_token(db_client, register_user):
    """A user sees and deletes only own items; a foreign id is the same 404."""
    first_id, first_token = register_user(email="first@example.com")
    second_id, second_token = register_user(email="second@example.com")
    first_headers = {"Authorization": f"Bearer {first_token}"}
    second_headers = {"Authorization": f"Bearer {second_token}"}

    created = db_client.post(
        "/profile/fridge",
        json={
            "product_name": "milk",
            "expiration_date": TOMORROW.isoformat(),
            "quantity": 2,
        },
        headers=first_headers,
    )
    assert created.status_code == 201
    item = created.get_json()
    assert item["user_id"] == first_id
    assert item["product_name"] == "milk"

    first_items = db_client.get("/profile/fridge", headers=first_headers).get_json()
    assert [row["id"] for row in first_items] == [item["id"]]
    assert db_client.get("/profile/fridge", headers=second_headers).get_json() == []

    forbidden = db_client.delete(f"/profile/fridge/{item['id']}", headers=second_headers)
    assert forbidden.status_code == 404
    assert "error" in forbidden.get_json()

    deleted = db_client.delete(f"/profile/fridge/{item['id']}", headers=first_headers)
    assert deleted.status_code == 200
    assert deleted.get_json() == {"message": f"Fridge item {item['id']} deleted"}
    assert db_client.get("/profile/fridge", headers=first_headers).get_json() == []


def test_profile_fridge_requires_a_token(client):
    """All personal fridge endpoints answer 401 without a Bearer token."""
    assert client.get("/profile/fridge").status_code == 401
    assert client.post("/profile/fridge", json={}).status_code == 401
    assert client.delete("/profile/fridge/1").status_code == 401
    assert client.delete("/profile/fridge/expired").status_code == 401


def test_add_profile_fridge_item_validates_the_payload(db_client, register_user):
    """The personal POST accepts only product_name, expiration_date and quantity."""
    _, token = register_user()
    headers = {"Authorization": f"Bearer {token}"}
    valid = {
        "product_name": "milk",
        "expiration_date": TOMORROW.isoformat(),
        "quantity": 1,
    }
    bad_payloads = [
        {},
        {"product_name": "milk"},
        {**valid, "quantity": 0},
        {**valid, "quantity": 1.5},
        {**valid, "product_name": "m" * 101},
        {**valid, "expiration_date": "01.01.2026"},
        "not an object",
    ]
    for payload in bad_payloads:
        response = db_client.post("/profile/fridge", json=payload, headers=headers)
        assert response.status_code == 400, payload
        assert "error" in response.get_json()

    # A user_id in the body is ignored: the owner still comes from the token.
    response = db_client.post(
        "/profile/fridge",
        json={**valid, "user_id": 999999},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.get_json()["user_id"] != 999999


def test_delete_profile_expired_items_affects_only_the_token_owner(
    db_client, register_user, add_relative_fridge_items, db
):
    """The personal cleanup deletes own expired rows and leaves another user untouched."""
    first_id, first_token = register_user(email="first@example.com")
    second_id, _ = register_user(email="second@example.com")
    add_relative_fridge_items(first_id, "old milk", -2)
    add_relative_fridge_items(first_id, "fresh bread", 1)
    add_relative_fridge_items(second_id, "old cheese", -2)

    response = db_client.delete(
        "/profile/fridge/expired",
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert response.status_code == 200
    assert response.get_json() == {"message": "Deleted 1 expired product(s)"}

    remaining = {
        (row["user_id"], row["product_name"])
        for row in db.fetch_all("SELECT user_id, product_name FROM fridge_items")
    }
    assert remaining == {(first_id, "fresh bread"), (second_id, "old cheese")}


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
