"""The database itself: the eight tables of ``docs/db_scheme.png``.

This file is the executable form of the ER diagram and covers everything that no
endpoint touches: column types, keys, the triggers that fill the fridge history
and the two tables of the diagram that have no API route yet
(``favorite_recipes`` and ``generated_recipes``, used through ``app.models``).

PostgreSQL is required, exactly like in the other database-backed tests.
"""

from __future__ import annotations

from datetime import date, timedelta

import psycopg2
import pytest
from psycopg2 import errors as pg_errors

from app.models import favorites as favorites_model
from app.models import generated as generated_model

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)

EXPECTED_TABLES = frozenset(
    {
        "users",
        "recipes",
        "fridge_items",
        "favorite_recipes",
        "generated_recipes",
        "user_allergy_preferences",
        "fridge_item_versions",
        "fridge_item_audit",
    }
)
# ``character varying`` columns are compared as (data type, maximum length).
EXPECTED_COLUMNS = {
    "users": {
        "id": ("integer", None),
        "username": ("character varying", 80),
        "password": ("character varying", 200),
        "email": ("character varying", 120),
        "allergies": ("text", None),
        "preferences": ("text", None),
    },
    "recipes": {
        "id": ("integer", None),
        "recipe_name": ("character varying", 200),
        "ingredients": ("text", None),
        "instruction": ("character varying", 100),
        "difficulty_level": ("character varying", 50),
    },
    "fridge_items": {
        "item_id": ("integer", None),
        "user_id": ("integer", None),
        "product_name": ("character varying", 100),
        "expiration_date": ("date", None),
        "quantity": ("integer", None),
        "last_added": ("timestamp without time zone", None),
    },
    "favorite_recipes": {
        "id": ("integer", None),
        "user_id": ("integer", None),
        "recipe_id": ("integer", None),
    },
    "generated_recipes": {
        "id": ("integer", None),
        "user_id": ("integer", None),
        "recipes_id": ("integer", None),
        "generated_on": ("timestamp without time zone", None),
    },
    "user_allergy_preferences": {
        "id": ("integer", None),
        "user_id": ("integer", None),
        "allergy_name": ("character varying", 100),
    },
    "fridge_item_versions": {
        "id": ("integer", None),
        "fridge_items_id": ("integer", None),
        "version": ("integer", None),
        "product_name": ("character varying", 100),
        "expiration_date": ("date", None),
        "quantity": ("integer", None),
        "updated_at": ("timestamp without time zone", None),
    },
    "fridge_item_audit": {
        "id": ("integer", None),
        "action_type": ("character varying", 50),
        "user_id": ("integer", None),
        "product_name": ("character varying", 100),
        "expiration_date": ("date", None),
        "quantity": ("integer", None),
        "action_time": ("timestamp without time zone", None),
        "old_values": ("jsonb", None),
        "new_value": ("jsonb", None),
    },
}
EXPECTED_PRIMARY_KEYS = {
    "users": {"id"},
    "recipes": {"id"},
    "fridge_items": {"item_id"},
    "favorite_recipes": {"id"},
    "generated_recipes": {"id"},
    "user_allergy_preferences": {"id"},
    "fridge_item_versions": {"id"},
    "fridge_item_audit": {"id"},
}
# (child table, child column) -> (parent table, parent column, ON DELETE rule)
EXPECTED_FOREIGN_KEYS = {
    ("fridge_items", "user_id"): ("users", "id", "CASCADE"),
    ("favorite_recipes", "user_id"): ("users", "id", "CASCADE"),
    ("favorite_recipes", "recipe_id"): ("recipes", "id", "CASCADE"),
    ("generated_recipes", "user_id"): ("users", "id", "CASCADE"),
    ("generated_recipes", "recipes_id"): ("recipes", "id", "CASCADE"),
    ("user_allergy_preferences", "user_id"): ("users", "id", "CASCADE"),
    ("fridge_item_versions", "fridge_items_id"): ("fridge_items", "item_id", "SET NULL"),
    ("fridge_item_audit", "user_id"): ("users", "id", "CASCADE"),
}

PRIMARY_KEY_SQL = """
    SELECT tc.table_name, kcu.column_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
        ON kcu.constraint_name = tc.constraint_name
       AND kcu.table_schema = tc.table_schema
    WHERE tc.table_schema = 'public' AND tc.constraint_type = 'PRIMARY KEY'
"""
FOREIGN_KEY_SQL = """
    SELECT kcu.table_name AS child_table,
           kcu.column_name AS child_column,
           ccu.table_name AS parent_table,
           ccu.column_name AS parent_column,
           rc.delete_rule
    FROM information_schema.referential_constraints AS rc
    JOIN information_schema.key_column_usage AS kcu
        ON kcu.constraint_name = rc.constraint_name
       AND kcu.table_schema = rc.constraint_schema
    JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = rc.unique_constraint_name
       AND ccu.table_schema = rc.unique_constraint_schema
    WHERE rc.constraint_schema = 'public'
"""
INSERT_USER_SQL = "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)"
INSERT_ITEM_SQL = """
    INSERT INTO fridge_items (user_id, product_name, expiration_date, quantity)
    VALUES (%s, %s, %s, %s)
"""
RECIPE_PAYLOAD = {
    "name": "Tomato pasta",
    "ingredients": "pasta, tomato, cheese",
    "instructions": "Boil the pasta.",
    "difficulty_level": "easy",
}
VERSION_SQL = """
    SELECT version, product_name, quantity
    FROM fridge_item_versions
    WHERE fridge_items_id = %s
    ORDER BY version
"""
AUDIT_SQL = """
    SELECT action_type, product_name, quantity, old_values, new_value
    FROM fridge_item_audit
    WHERE user_id = %s
    ORDER BY id
"""


def _columns(db) -> dict[str, dict[str, tuple[str, int | None]]]:
    """Return ``{table: {column: (data type, max length)}}`` for the public schema."""
    rows = db.fetch_all(
        """
        SELECT table_name, column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'public'
        """
    )
    columns: dict[str, dict[str, tuple[str, int | None]]] = {}
    for row in rows:
        columns.setdefault(row["table_name"], {})[row["column_name"]] = (
            row["data_type"],
            row["character_maximum_length"],
        )
    return columns


def _recipe_id(db_client, db) -> int:
    """Create one recipe through the API and return its primary key."""
    assert db_client.post("/recipes", json=RECIPE_PAYLOAD).status_code == 201
    return int(db.fetch_one("SELECT id FROM recipes")["id"])


def _item_id(db) -> int:
    """Return the primary key of the only fridge item in the database."""
    return int(db.fetch_one("SELECT item_id FROM fridge_items")["item_id"])


def test_tables_columns_and_primary_keys_match_the_diagram(db):
    """The eight tables, their column types and the primary keys of the diagram."""
    tables = {
        row["table_name"]
        for row in db.fetch_all(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """
        )
    }
    # schema_migrations belongs to app/migrate.py and is optional here.
    assert tables - {"schema_migrations"} == EXPECTED_TABLES

    columns = _columns(db)
    for table, expected in EXPECTED_COLUMNS.items():
        assert columns[table] == expected, table
    # cuisine_type was removed from the diagram and from openapi.yaml.
    assert "cuisine_type" not in columns["recipes"]

    keys: dict[str, set[str]] = {}
    for row in db.fetch_all(PRIMARY_KEY_SQL):
        keys.setdefault(row["table_name"], set()).add(row["column_name"])
    keys.pop("schema_migrations", None)
    assert keys == EXPECTED_PRIMARY_KEYS


def test_foreign_keys_and_the_email_index_match_the_diagram(db):
    found = {
        (row["child_table"], row["child_column"]): (
            row["parent_table"],
            row["parent_column"],
            row["delete_rule"],
        )
        for row in db.fetch_all(FOREIGN_KEY_SQL)
    }
    assert found == EXPECTED_FOREIGN_KEYS

    # E-mails are case-insensitive (openapi.yaml), so the unique index uses lower(email).
    indexes = {
        row["indexname"]: row["indexdef"].lower()
        for row in db.fetch_all(
            """
            SELECT indexname, indexdef FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = 'users'
            """
        )
    }
    assert "users_email_lower_key" in indexes
    assert "unique" in indexes["users_email_lower_key"]
    assert "lower(email)" in indexes["users_email_lower_key"]


def test_triggers_and_functions_of_the_fridge_history_exist(db):
    triggers = db.fetch_all(
        """
        SELECT tgname FROM pg_trigger
        WHERE tgrelid = 'fridge_items'::regclass AND NOT tgisinternal
        """
    )
    assert {row["tgname"] for row in triggers} == {
        "fridge_items_version_trigger",
        "fridge_items_audit_trigger",
    }
    functions = db.fetch_all(
        "SELECT proname FROM pg_proc WHERE proname = ANY(%s)",
        (["fridge_items_log_version", "fridge_items_log_audit"],),
    )
    assert {row["proname"] for row in functions} == {
        "fridge_items_log_version",
        "fridge_items_log_audit",
    }


def test_database_constraints_are_enforced(db, register_user):
    """The rules of the diagram are enforced by PostgreSQL, not only by the API."""
    user_id, _ = register_user()

    with pytest.raises(psycopg2.errors.CheckViolation):  # CHECK (quantity > 0)
        db.execute(INSERT_ITEM_SQL, (user_id, "milk", TOMORROW, 0))
    with pytest.raises(psycopg2.errors.NotNullViolation):  # users.password is NOT NULL
        db.execute(INSERT_USER_SQL, ("ghost", "ghost@example.com", None))
    with pytest.raises(psycopg2.errors.UniqueViolation):  # users.username is unique
        db.execute(INSERT_USER_SQL, ("tester", "other@example.com", "scrypt:placeholder"))
    with pytest.raises(psycopg2.errors.UniqueViolation):  # the e-mail is unique ignoring case
        db.execute(INSERT_USER_SQL, ("other", "TESTER@example.com", "scrypt:placeholder"))


def test_fridge_history_records_the_insert_and_the_update(
    db_client, register_user, add_fridge_items, db
):
    """fridge_item_versions and fridge_item_audit are filled by the triggers."""
    user_id, _ = register_user()
    add_fridge_items(user_id, "milk", TOMORROW, quantity=2)

    # INSERT -> first version, audit entry without old_values.
    assert db.fetch_all(VERSION_SQL, (_item_id(db),)) == [
        {"version": 1, "product_name": "milk", "quantity": 2}
    ]
    entries = db.fetch_all(AUDIT_SQL, (user_id,))
    assert entries[0]["action_type"] == "INSERT"
    assert entries[0]["old_values"] is None
    assert entries[0]["new_value"]["product_name"] == "milk"

    # UPDATE -> one more version and old/new snapshots in the audit table.
    db.execute(
        "UPDATE fridge_items SET product_name = %s, quantity = %s WHERE user_id = %s",
        ("sour milk", 5, user_id),
    )
    versions = db.fetch_all(VERSION_SQL, (_item_id(db),))
    assert [version["version"] for version in versions] == [1, 2]
    assert versions[1]["product_name"] == "sour milk"
    assert versions[1]["quantity"] == 5

    entries = db.fetch_all(AUDIT_SQL, (user_id,))
    assert [entry["action_type"] for entry in entries] == ["INSERT", "UPDATE"]
    assert entries[1]["old_values"]["quantity"] == 1
    assert entries[1]["new_value"]["quantity"] == 5


def test_fridge_history_survives_the_delete_of_a_product_and_of_a_user(
    db_client, register_user, add_fridge_items, db
):
    """ON DELETE SET NULL keeps the versions, the audit trigger never blocks a delete."""
    user_id, _ = register_user()
    add_fridge_items(user_id, "old milk", YESTERDAY)

    # Deleting an expired product is logged and keeps the version row of the item.
    response = db_client.delete("/delete_expired_products")
    assert response.get_json() == {"message": "Deleted 1 expired product(s)"}
    entries = db.fetch_all(AUDIT_SQL, (user_id,))
    assert [entry["action_type"] for entry in entries] == ["INSERT", "DELETE"]
    assert entries[1]["new_value"] is None
    assert db.fetch_all(
        "SELECT fridge_items_id, version FROM fridge_item_versions ORDER BY id"
    ) == [{"fridge_items_id": None, "version": 1}]

    # Deleting a user cascades into the fridge and the audit table, the versions stay.
    other, _ = register_user(email="other@example.com")
    add_fridge_items(other, "milk", TOMORROW)
    assert db.execute("DELETE FROM users WHERE id = %s", (other,)) == 1
    assert db.fetch_all("SELECT item_id FROM fridge_items WHERE user_id = %s", (other,)) == []
    assert db.fetch_all("SELECT id FROM fridge_item_audit WHERE user_id = %s", (other,)) == []
    assert db.fetch_all(
        "SELECT fridge_items_id, version FROM fridge_item_versions ORDER BY id"
    ) == [{"fridge_items_id": None, "version": 1}, {"fridge_items_id": None, "version": 1}]


def test_favorite_recipes_are_unique_and_cascade(db_client, register_user, db):
    """favorite_recipes has no API route yet, so the model functions are its API."""
    user_id, _ = register_user()
    recipe_id = _recipe_id(db_client, db)

    assert favorites_model.add_favorite(db, user_id, recipe_id) is True
    assert favorites_model.is_favorite(db, user_id, recipe_id) is True
    assert favorites_model.recipe_ids(db, user_id) == [recipe_id]
    listed = favorites_model.list_favorites(db, user_id)
    assert [row["recipe_name"] for row in listed] == [RECIPE_PAYLOAD["name"]]

    # The unique constraint keeps the same pair of ids from being stored twice.
    assert favorites_model.add_favorite(db, user_id, recipe_id) is False
    assert favorites_model.recipe_ids(db, user_id) == [recipe_id]

    # The recipe must exist (foreign key to recipes.id).
    with pytest.raises(pg_errors.ForeignKeyViolation):
        favorites_model.add_favorite(db, user_id, 999999)

    assert favorites_model.remove_favorite(db, user_id, recipe_id) is True
    assert favorites_model.remove_favorite(db, user_id, recipe_id) is False
    assert favorites_model.recipe_ids(db, user_id) == []

    # Deleting a recipe removes its favourites (ON DELETE CASCADE).
    favorites_model.add_favorite(db, user_id, recipe_id)
    assert db.execute("DELETE FROM recipes WHERE id = %s", (recipe_id,)) == 1
    assert favorites_model.recipe_ids(db, user_id) == []


def test_generated_recipes_keep_what_was_offered(db_client, register_user, db):
    """generated_recipes is written by /suggest_recipes and /recommend_recipes."""
    user_id, _ = register_user()
    recipe_id = _recipe_id(db_client, db)

    assert generated_model.record_generated(db, user_id, [recipe_id]) == 1
    rows = generated_model.list_generated(db, user_id)
    assert rows[0]["recipes_id"] == recipe_id
    assert rows[0]["generated_on"] is not None
    offered = generated_model.list_recipes_for_user(db, user_id)
    assert [row["recipe_name"] for row in offered] == [RECIPE_PAYLOAD["name"]]

    # An empty suggestion writes nothing.
    assert generated_model.record_generated(db, user_id, []) == 0
    assert len(generated_model.list_generated(db, user_id)) == 1

    # The recipe must exist (foreign key to recipes.id).
    with pytest.raises(pg_errors.ForeignKeyViolation):
        generated_model.record_generated(db, user_id, [999999])

    assert generated_model.delete_generated(db, user_id) == 1
    assert generated_model.list_generated(db, user_id) == []

    # Deleting a recipe removes its history entries (ON DELETE CASCADE).
    generated_model.record_generated(db, user_id, [recipe_id])
    assert db.execute("DELETE FROM recipes WHERE id = %s", (recipe_id,)) == 1
    assert generated_model.list_generated(db, user_id) == []
