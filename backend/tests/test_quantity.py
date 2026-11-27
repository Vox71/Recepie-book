"""Normalization of the free-form amounts of the dataset."""

from __future__ import annotations

from decimal import Decimal

from app.importer.quantity import backfill_quantities, parse_quantity


def test_parse_quantity_canonicalizes_mass_and_volume():
    assert parse_quantity("250 мл").value == Decimal("250")
    assert parse_quantity("250 мл").unit == "мл"
    assert parse_quantity("1 кг").value == Decimal("1000")
    assert parse_quantity("1 кг").unit == "г"
    assert parse_quantity("1,5 л").value == Decimal("1500")
    assert parse_quantity("1,5 л").unit == "мл"


def test_parse_quantity_keeps_countable_units():
    assert parse_quantity("3 шт").value == Decimal("3")
    assert parse_quantity("3 шт").unit == "шт."
    assert parse_quantity("1,5 ст. л.").value == Decimal("1.5")
    assert parse_quantity("1,5 ст. л.").unit == "ст. л."
    assert parse_quantity("1/2 ч. л.").value == Decimal("0.5")
    assert parse_quantity("1/2 ч. л.").unit == "ч. л."


def test_parse_quantity_does_not_invent_a_number():
    assert parse_quantity("по вкусу").value is None
    assert parse_quantity("1–2 шт.").value is None
    assert parse_quantity(None).value is None


def test_parse_quantity_without_a_unit_keeps_the_number():
    parsed = parse_quantity("2")
    assert parsed.value == Decimal("2")
    assert parsed.unit is None


def test_backfill_fills_only_normalizable_rows(db):
    db.execute("INSERT INTO recipes (recipe_name, ingredients) VALUES ('Суп', 'Вода — 1 л, Соль')")
    recipe_id = int(db.fetch_one("SELECT id FROM recipes WHERE recipe_name = 'Суп'")["id"])
    db.execute(
        """
        INSERT INTO recipe_ingredients (recipe_id, ingredient_name, quantity_text, sort_order)
        VALUES (%s, 'Вода', '1 л', 0), (%s, 'Соль', 'по вкусу', 1)
        """,
        (recipe_id, recipe_id),
    )

    assert backfill_quantities(db) == 1
    water = db.fetch_one(
        "SELECT quantity_value, quantity_unit FROM recipe_ingredients "
        "WHERE recipe_id = %s AND ingredient_name = 'Вода'",
        (recipe_id,),
    )
    salt = db.fetch_one(
        "SELECT quantity_value, quantity_unit FROM recipe_ingredients "
        "WHERE recipe_id = %s AND ingredient_name = 'Соль'",
        (recipe_id,),
    )
    assert water == {"quantity_value": 1000, "quantity_unit": "мл"}
    assert salt == {"quantity_value": None, "quantity_unit": None}
