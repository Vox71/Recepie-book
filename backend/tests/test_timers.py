"""Timers: ``/timers`` (start), ``/timers/active`` (list) and ``/timers/{id}`` (cancel).

Sprint 3, task 1, user story "как пользователь, я хочу видеть таймеры в рецепте, чтобы
было удобнее засекать время".

The rules checked here are the ones that make a timer reliable:

* the deadline is computed by the database (``started_at + duration``), not by the
  process, so a restart or a second worker cannot shift it;
* a recipe without ``cooking_time_minutes`` cannot hide the missing duration: the client
  must send ``duration_seconds`` explicitly (imported recipes have no time at all);
* the owner always comes from the token, and a timer of another user is a 404;
* an expired timer is closed by the read itself, so no background worker is needed.

The countdown itself lives in the browser (``docs/timer.md``): the answer carries
``ends_at`` and ``server_time``, and the client renders the difference with a monotonic
clock, so these tests assert the pair, not a ticking counter.
"""

from __future__ import annotations

from datetime import datetime

RECIPE = {
    "name": "Гречка",
    "ingredients": "гречка — 200 г, вода — 400 мл",
    "instructions": "Варить 15 минут.",
    "difficulty_level": "easy",
    "cooking_time_minutes": 15,
}


def _create_recipe(db_client, name: str = RECIPE["name"], **overrides) -> int:
    """Create a recipe through the API and return its id."""
    payload = {**RECIPE, "name": name, **overrides}
    assert db_client.post("/recipes", json=payload).status_code == 201
    return next(item["id"] for item in db_client.get("/recipes").get_json() if item["name"] == name)


def _start(db_client, token: str, **payload) -> dict:
    """Start a timer and return the JSON body; ``recipe_id`` is required."""
    headers = {"Authorization": f"Bearer {token}"}
    response = db_client.post("/timers", json=payload, headers=headers)
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def _seconds_between(started_at: str, ends_at: str) -> float:
    """Difference of two ISO 8601 timestamps, in seconds."""
    return (datetime.fromisoformat(ends_at) - datetime.fromisoformat(started_at)).total_seconds()


def test_a_timer_is_created_from_the_recipe_time(db_client, register_user):
    """Without ``duration_seconds`` the server takes ``cooking_time_minutes`` × 60."""
    _, token = register_user()
    recipe_id = _create_recipe(db_client, cooking_time_minutes=2)

    body = _start(db_client, token, recipe_id=recipe_id)

    assert set(body) == {"server_time", "timer"}
    timer = body["timer"]
    assert set(timer) == {
        "id",
        "recipe_id",
        "label",
        "duration_seconds",
        "started_at",
        "ends_at",
        "remaining_seconds",
        "status",
    }
    assert timer["recipe_id"] == recipe_id
    assert timer["duration_seconds"] == 120
    # The label defaults to the recipe name, so a client shows the list without a join.
    assert timer["label"] == "Гречка"
    assert timer["status"] == "running"
    assert _seconds_between(timer["started_at"], timer["ends_at"]) == 120
    # The reference pair for the client: both values come from the same statement.
    assert 0 < timer["remaining_seconds"] <= 120
    assert datetime.fromisoformat(body["server_time"]) <= datetime.fromisoformat(timer["ends_at"])


def test_a_recipe_without_cooking_time_requires_a_duration(db_client, register_user):
    """An imported recipe has no time: 400 instead of a timer of an unknown length."""
    _, token = register_user()
    recipe_id = _create_recipe(db_client, name="Уха", cooking_time_minutes=None)
    headers = {"Authorization": f"Bearer {token}"}

    missing = db_client.post("/timers", json={"recipe_id": recipe_id}, headers=headers)
    assert missing.status_code == 400, missing.get_json()
    assert "cooking time" in missing.get_json()["error"]

    explicit = db_client.post(
        "/timers", json={"recipe_id": recipe_id, "duration_seconds": 90}, headers=headers
    )
    assert explicit.status_code == 201, explicit.get_json()
    assert explicit.get_json()["timer"]["duration_seconds"] == 90


def test_a_timer_requires_an_existing_recipe(db_client, register_user):
    """``recipe_id`` is mandatory, an unknown recipe is the documented 404."""
    _, token = register_user()
    headers = {"Authorization": f"Bearer {token}"}

    assert db_client.post("/timers", json={}, headers=headers).status_code == 400
    assert db_client.post("/timers", json={"recipe_id": 0}, headers=headers).status_code == 400
    unknown = db_client.post("/timers", json={"recipe_id": 424242}, headers=headers)
    assert unknown.status_code == 404, unknown.get_json()
    assert "424242" in unknown.get_json()["error"]
    assert db_client.post("/timers", json="not an object", headers=headers).status_code == 400

    # An explicit duration is enough even for a recipe that has its own time.
    recipe_id = _create_recipe(db_client)
    body = _start(db_client, token, recipe_id=recipe_id, duration_seconds=5, label="  Вода  ")
    assert body["timer"]["duration_seconds"] == 5
    assert body["timer"]["label"] == "Вода"


def test_the_deadline_is_started_at_plus_duration(db_client, db, register_user):
    """The deadline is a property of the row: the database computes both timestamps."""
    _, token = register_user()
    recipe_id = _create_recipe(db_client)

    timer = _start(db_client, token, recipe_id=recipe_id, duration_seconds=90)["timer"]

    row = db.fetch_one(
        """
        SELECT started_at, ends_at, status, closed_at,
               EXTRACT(EPOCH FROM ends_at - started_at) AS duration,
               EXTRACT(EPOCH FROM ends_at - now()) AS remaining
        FROM timers WHERE id = %s
        """,
        (timer["id"],),
    )
    assert float(row["duration"]) == 90
    assert 0 < float(row["remaining"]) <= 90
    assert row["status"] == "running"
    assert row["closed_at"] is None


def test_timers_are_isolated_by_the_token(db_client, register_user):
    """The owner comes from the token: a foreign timer is invisible and cannot be stopped."""
    _, token = register_user(email="first@example.com")
    _, other_token = register_user(email="second@example.com")
    recipe_id = _create_recipe(db_client)

    timer = _start(db_client, token, recipe_id=recipe_id, duration_seconds=600)["timer"]
    first_headers = {"Authorization": f"Bearer {token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}

    mine = db_client.get("/timers/active", headers=first_headers).get_json()["timers"]
    assert [item["id"] for item in mine] == [timer["id"]]
    assert db_client.get("/timers/active", headers=other_headers).get_json()["timers"] == []
    # 404, not 403: the answer does not disclose whether the row exists.
    assert db_client.delete(f"/timers/{timer['id']}", headers=other_headers).status_code == 404


def test_an_active_timer_survives_a_reload(db_client, register_user):
    """The list is the state: a reload gets the same timer back with a fresh pair."""
    _, token = register_user()
    recipe_id = _create_recipe(db_client)
    headers = {"Authorization": f"Bearer {token}"}

    created = _start(db_client, token, recipe_id=recipe_id, duration_seconds=300)["timer"]
    body = db_client.get("/timers/active", headers=headers).get_json()

    assert set(body) == {"server_time", "timers"}
    assert [item["id"] for item in body["timers"]] == [created["id"]]
    restored = body["timers"][0]
    assert restored["ends_at"] == created["ends_at"]
    assert restored["remaining_seconds"] <= created["remaining_seconds"]
    assert datetime.fromisoformat(body["server_time"]) <= datetime.fromisoformat(
        restored["ends_at"]
    )


def test_an_expired_timer_is_closed_lazily(db_client, db, register_user):
    """Reading the list closes expired timers: no background worker is needed."""
    _, token = register_user()
    recipe_id = _create_recipe(db_client)
    timer = _start(db_client, token, recipe_id=recipe_id, duration_seconds=60)["timer"]

    # Move the deadline into the past instead of waiting a minute.
    db.execute(
        """
        UPDATE timers
        SET started_at = now() - interval '61 seconds', ends_at = now() - interval '1 second'
        WHERE id = %s
        """,
        (timer["id"],),
    )

    headers = {"Authorization": f"Bearer {token}"}
    assert db_client.get("/timers/active", headers=headers).get_json()["timers"] == []
    row = db.fetch_one(
        "SELECT status, closed_at = ends_at AS closed_on_time FROM timers WHERE id = %s",
        (timer["id"],),
    )
    assert row == {"status": "finished", "closed_on_time": True}
    # A finished timer cannot be cancelled twice: the answer is the documented 404.
    assert db_client.delete(f"/timers/{timer['id']}", headers=headers).status_code == 404


def test_cancel_removes_the_timer_from_active(db_client, db, register_user):
    """``DELETE /timers/{id}`` stops the timer once; a repeat is a 404."""
    _, token = register_user()
    recipe_id = _create_recipe(db_client)
    headers = {"Authorization": f"Bearer {token}"}
    timer = _start(db_client, token, recipe_id=recipe_id, duration_seconds=600)["timer"]

    cancelled = db_client.delete(f"/timers/{timer['id']}", headers=headers)
    assert cancelled.status_code == 200
    assert "cancelled" in cancelled.get_json()["message"]
    assert db_client.get("/timers/active", headers=headers).get_json()["timers"] == []
    assert db_client.delete(f"/timers/{timer['id']}", headers=headers).status_code == 404
    assert db.fetch_one("SELECT status FROM timers WHERE id = %s", (timer["id"],)) == {
        "status": "cancelled"
    }


def test_the_active_timers_are_ordered_and_capped(db_client, register_user):
    """The list is ordered by the deadline and a client cannot fill the table forever."""
    _, token = register_user()
    recipe_id = _create_recipe(db_client)
    headers = {"Authorization": f"Bearer {token}"}

    for duration in (300, 100, 200):
        _start(db_client, token, recipe_id=recipe_id, duration_seconds=duration)
    active = db_client.get("/timers/active", headers=headers).get_json()["timers"]
    assert [item["duration_seconds"] for item in active] == [100, 200, 300]

    # 20 active timers is the limit (MAX_ACTIVE_TIMERS), the 21st is a 400.
    for _ in range(17):
        _start(db_client, token, recipe_id=recipe_id, duration_seconds=600)
    limited = db_client.post(
        "/timers", json={"recipe_id": recipe_id, "duration_seconds": 600}, headers=headers
    )
    assert limited.status_code == 400, limited.get_json()
    assert "timers can run at once" in limited.get_json()["error"]


def test_timer_payloads_are_validated(db_client, register_user):
    """Every wrong duration, label or body is a 400 with the usual error object."""
    _, token = register_user()
    recipe_id = _create_recipe(db_client)
    headers = {"Authorization": f"Bearer {token}"}

    bad_bodies = [
        {"recipe_id": recipe_id, "duration_seconds": 0},
        {"recipe_id": recipe_id, "duration_seconds": 86401},
        {"recipe_id": recipe_id, "duration_seconds": "10"},
        {"recipe_id": recipe_id, "duration_seconds": True},
        {"recipe_id": recipe_id, "duration_seconds": 10, "label": "x" * 101},
        {"recipe_id": "not a number"},
    ]
    for payload in bad_bodies:
        response = db_client.post("/timers", json=payload, headers=headers)
        assert response.status_code == 400, payload
        assert "error" in response.get_json()

    # The upper bound itself is accepted: a timer of a whole day.
    assert (
        db_client.post(
            "/timers", json={"recipe_id": recipe_id, "duration_seconds": 86400}, headers=headers
        ).status_code
        == 201
    )


def test_timers_require_a_token(client):
    """All three addresses are personal, so a request without a token is a 401."""
    assert client.post("/timers", json={"recipe_id": 1}).status_code == 401
    assert client.get("/timers/active").status_code == 401
    assert client.delete("/timers/1").status_code == 401
