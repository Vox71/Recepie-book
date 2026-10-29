"""Import of the povarenok dataset: parsing, file formats, idempotency and the CLI.

The dataset itself is not in the repository (its licence is not stated), therefore the
tests use the synthetic sample ``tests/data/povarenok_sample.json`` and small files
written into ``tmp_path``. The sample has 12 recipes and 60 ingredient lines; it also
covers the shapes of the ``ingredients`` column: a mapping, a stringified mapping and a
list of ``"name: quantity"`` lines.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from app.importer import cli
from app.importer.povarenok import (
    NO_INGREDIENTS_TEXT,
    DatasetError,
    Ingredient,
    import_dataset,
    iter_rows,
    parse_ingredients,
    record_from_row,
    render_ingredients,
)
from app.importer.source import download_dataset

SAMPLE = Path(__file__).with_name("data") / "povarenok_sample.json"
SAMPLE_RECIPES = 12
SAMPLE_INGREDIENTS = 60


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8"
    )
    return path


def test_record_from_row_normalizes_the_dataset_values():
    record = record_from_row(
        {
            "url": "  https://www.povarenok.ru/recipes/show/1/  ",
            "name": "  Оливье\u00a0классический  ",
            "ingredients": {
                "  Мука  пшеничная ": " 300   г ",
                "Соль": "",
                "мука пшеничная": "1 кг",
                "": "2 шт.",
            },
        }
    )
    assert record is not None
    assert record.source_url == "https://www.povarenok.ru/recipes/show/1/"
    assert record.name == "Оливье классический"
    # A repeated name (case-insensitive), a blank name and a blank amount are handled,
    # because recipe_ingredients has UNIQUE (recipe_id, ingredient_name) and a nullable
    # quantity_text.
    assert record.ingredients == (
        Ingredient(name="Мука пшеничная", quantity="300 г"),
        Ingredient(name="Соль", quantity=None),
    )
    assert record.ingredients_text == "Мука пшеничная — 300 г, Соль"


def test_record_from_row_rejects_unusable_rows():
    assert record_from_row({}) is None
    assert record_from_row({"url": "ftp://example.com/1", "name": "Суп"}) is None
    assert record_from_row({"url": "https://example.com/1", "name": "   "}) is None
    # recipes.source_url is varchar(255), recipes.recipe_name is varchar(200).
    assert record_from_row({"url": "https://example.com/" + "1" * 300, "name": "Суп"}) is None
    assert record_from_row({"url": "https://example.com/1", "name": "я" * 201}) is None


def test_parse_ingredients_accepts_the_dataset_shapes():
    assert parse_ingredients(None) == ()
    assert parse_ingredients("") == ()
    assert parse_ingredients({"Мука": "300 г", "Соль": None}) == (
        Ingredient(name="Мука", quantity="300 г"),
        Ingredient(name="Соль", quantity=None),
    )
    # A CSV export keeps the mapping as text, an older dump as "name: amount" lines.
    assert parse_ingredients('{"Мука": "300 г"}') == (Ingredient(name="Мука", quantity="300 г"),)
    # pandas writes a Python literal, not JSON: single quotes and None for no amount.
    assert parse_ingredients("{'Яйцо куриное': '5 шт', 'Соль': None}") == (
        Ingredient(name="Яйцо куриное", quantity="5 шт"),
        Ingredient(name="Соль", quantity=None),
    )
    assert parse_ingredients("Мука: 300 г; Соль: щепотка\nСахар") == (
        Ingredient(name="Мука", quantity="300 г"),
        Ingredient(name="Соль", quantity="щепотка"),
        Ingredient(name="Сахар", quantity=None),
    )
    assert parse_ingredients([{"Мука": "300 г"}, "Соль: щепотка"]) == (
        Ingredient(name="Мука", quantity="300 г"),
        Ingredient(name="Соль", quantity="щепотка"),
    )
    # A recipe without ingredients arrives as an empty cell or "nan" from pandas.
    for empty in ("", "  ", "nan", "NaN", "None", None, float("nan")):
        assert parse_ingredients(empty) == (), empty
    # recipes.ingredients is NOT NULL, so an empty list still renders as text.
    assert render_ingredients(()) == NO_INGREDIENTS_TEXT


def test_iter_rows_reads_json_csv_and_jsonl(tmp_path):
    rows = [{"url": "https://example.com/1", "name": "Суп", "ingredients": {"Мука": "300 г"}}]
    json_path = tmp_path / "rows.json"
    json_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    jsonl_path = _write_jsonl(tmp_path / "rows.jsonl", rows)

    csv_path = tmp_path / "rows.csv"
    csv_path.write_text(
        "url,name,ingredients\n"
        # The real export is written by pandas: a Python literal and an empty cell for a
        # recipe without ingredients.
        "https://example.com/1,Суп,\"{'Мука': '300 г', 'Соль': None}\"\n"
        "https://example.com/2,Пустая кастрюля,\n",
        encoding="utf-8",
    )

    for path in (json_path, jsonl_path):
        assert [row["name"] for row in iter_rows(path)] == ["Суп"], path

    csv_rows = list(iter_rows(csv_path))
    assert [row["name"] for row in csv_rows] == ["Суп", "Пустая кастрюля"]
    assert record_from_row(csv_rows[0]).ingredients == (
        Ingredient(name="Мука", quantity="300 г"),
        Ingredient(name="Соль", quantity=None),
    )
    assert record_from_row(csv_rows[1]).ingredients_text == NO_INGREDIENTS_TEXT

    # A CSV without the dataset columns is a clear error, not an empty import.
    broken_csv = tmp_path / "broken.csv"
    broken_csv.write_text("title,text\nСуп,вкусный\n", encoding="utf-8")
    with pytest.raises(DatasetError):
        list(iter_rows(broken_csv))

    unsupported = tmp_path / "rows.xlsx"
    unsupported.write_text("not a dataset", encoding="utf-8")
    with pytest.raises(DatasetError):
        list(iter_rows(unsupported))


def test_import_dataset_dry_run_does_not_need_a_database(tmp_path):
    stats = import_dataset(None, SAMPLE, dry_run=True)
    assert stats.as_dict()["dry_run"] is True
    assert stats.rows_read == SAMPLE_RECIPES
    assert stats.recipes_parsed == SAMPLE_RECIPES
    assert stats.ingredients_parsed == SAMPLE_INGREDIENTS
    assert stats.recipes_inserted == 0
    assert stats.ingredients_inserted == 0

    limited = import_dataset(None, SAMPLE, dry_run=True, limit=3)
    assert (limited.rows_read, limited.recipes_parsed) == (3, 3)

    broken = _write_jsonl(
        tmp_path / "broken.jsonl",
        [
            {"url": "https://example.com/1", "name": "Суп", "ingredients": {"Мука": "300 г"}},
            {"url": "", "name": "Без ссылки", "ingredients": {"Соль": "1 щепот."}},
        ],
    )
    parsed = import_dataset(None, broken, dry_run=True)
    assert (parsed.recipes_parsed, parsed.records_skipped) == (1, 1)


def test_download_dataset_unpacks_the_archive_and_sends_the_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("KAGGLE_USERNAME", "kaggle-user")
    monkeypatch.setenv("KAGGLE_KEY", "kaggle-key")
    payload = SAMPLE.read_bytes()
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("recipes.json", payload)

    seen: dict[str, object] = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["authorization"] = request.get_header("Authorization")
        return io.BytesIO(archive_bytes.getvalue())

    path = download_dataset(tmp_path, timeout=7, opener=opener)

    assert path == tmp_path / "recipes.json"
    assert path.read_bytes() == payload
    assert seen["timeout"] == 7
    assert str(seen["url"]).endswith("/rogozinushka/povarenok-recipes")
    assert str(seen["authorization"]).startswith("Basic ")
    # The archive itself is not kept next to the data.
    assert not (tmp_path / "povarenok-recipes.zip").exists()


def test_download_dataset_requires_the_kaggle_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.delenv("KAGGLE_KEY", raising=False)
    with pytest.raises(DatasetError):
        download_dataset(tmp_path)


def test_cli_dry_run_and_error_codes(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POVARENOK_DATASET", raising=False)

    # Without a dataset there is nothing to parse.
    assert cli.main(["--dataset", str(tmp_path / "missing.json"), "--dry-run"]) == cli.EXIT_FAILED
    # A real run needs DATABASE_URL, a dry run does not.
    assert cli.main(["--dataset", str(SAMPLE)]) == cli.EXIT_CONFIGURATION
    assert cli.main(["--dataset", str(SAMPLE), "--dry-run"]) == cli.EXIT_OK

    # The path may come from the environment (the plan's command has no --dataset).
    monkeypatch.setenv("POVARENOK_DATASET", str(SAMPLE))
    assert cli.main(["--dry-run", "--limit", "2"]) == cli.EXIT_OK


def test_import_fills_recipes_and_recipe_ingredients(db):
    stats = import_dataset(db, SAMPLE, batch_size=5)
    assert stats.recipes_inserted == SAMPLE_RECIPES
    assert stats.recipes_duplicated == 0
    assert stats.ingredients_inserted == SAMPLE_INGREDIENTS

    assert db.fetch_one("SELECT count(*) AS rows FROM recipes")["rows"] == SAMPLE_RECIPES
    assert (
        db.fetch_one("SELECT count(*) AS rows FROM recipe_ingredients")["rows"]
        == SAMPLE_INGREDIENTS
    )

    # The dataset has no instruction and no difficulty, so the columns stay NULL and the
    # recipe is recognised by source_url (docs/db_schema.md).
    recipe = db.fetch_one(
        """
        SELECT id, recipe_name, ingredients, instruction, difficulty_level, source_url
        FROM recipes
        WHERE source_url = %s
        """,
        ("https://www.povarenok.ru/recipes/show/101/",),
    )
    assert recipe["recipe_name"] == "Оливье классический"
    assert recipe["instruction"] is None
    assert recipe["difficulty_level"] is None
    assert recipe["ingredients"].startswith("Картофель — 4 шт., Морковь — 2 шт.")

    lines = db.fetch_all(
        """
        SELECT ingredient_name, quantity_text, sort_order
        FROM recipe_ingredients
        WHERE recipe_id = %s
        ORDER BY sort_order
        """,
        (recipe["id"],),
    )
    assert [line["ingredient_name"] for line in lines][:3] == [
        "Картофель",
        "Морковь",
        "Яйцо куриное",
    ]
    assert lines[0] == {"ingredient_name": "Картофель", "quantity_text": "4 шт.", "sort_order": 0}

    # An amount that the source does not give stays NULL (Соль in the "Сырники" row).
    salt = db.fetch_one(
        """
        SELECT ri.quantity_text
        FROM recipe_ingredients AS ri
        JOIN recipes AS r ON r.id = ri.recipe_id
        WHERE r.source_url = %s AND ri.ingredient_name = 'Соль'
        """,
        ("https://www.povarenok.ru/recipes/show/103/",),
    )
    assert salt["quantity_text"] is None

    # The stringified mapping and the list of lines are parsed as well.
    pizza = db.fetch_one(
        "SELECT count(*) AS rows FROM recipe_ingredients WHERE recipe_id = "
        "(SELECT id FROM recipes WHERE source_url = %s)",
        ("https://www.povarenok.ru/recipes/show/111/",),
    )
    assert pizza["rows"] == 6
    compote = db.fetch_one(
        "SELECT count(*) AS rows FROM recipe_ingredients WHERE recipe_id = "
        "(SELECT id FROM recipes WHERE source_url = %s)",
        ("https://www.povarenok.ru/recipes/show/112/",),
    )
    assert compote["rows"] == 4


def test_repeated_import_is_idempotent_and_honours_the_limit(db):
    partial = import_dataset(db, SAMPLE, limit=3, batch_size=2)
    assert partial.recipes_inserted == 3
    assert db.fetch_one("SELECT count(*) AS rows FROM recipes")["rows"] == 3

    # A second run adds the missing recipes and repeats the first three.
    full = import_dataset(db, SAMPLE, batch_size=5)
    assert full.recipes_inserted == SAMPLE_RECIPES - 3
    assert full.recipes_duplicated == 3

    again = import_dataset(db, SAMPLE, batch_size=5)
    assert (again.recipes_inserted, again.ingredients_inserted) == (0, 0)
    assert again.recipes_duplicated == SAMPLE_RECIPES
    assert db.fetch_one("SELECT count(*) AS rows FROM recipes")["rows"] == SAMPLE_RECIPES
    assert (
        db.fetch_one("SELECT count(*) AS rows FROM recipe_ingredients")["rows"]
        == SAMPLE_INGREDIENTS
    )


def test_cli_imports_the_sample(db, database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("AUTO_INIT_SCHEMA", "true")

    assert cli.main(["--dataset", str(SAMPLE), "--batch-size", "5"]) == cli.EXIT_OK
    assert db.fetch_one("SELECT count(*) AS rows FROM recipes")["rows"] == SAMPLE_RECIPES
    assert (
        db.fetch_one("SELECT count(*) AS rows FROM recipe_ingredients")["rows"]
        == SAMPLE_INGREDIENTS
    )

    # The same command again changes nothing.
    assert cli.main(["--dataset", str(SAMPLE), "--batch-size", "5"]) == cli.EXIT_OK
    assert db.fetch_one("SELECT count(*) AS rows FROM recipes")["rows"] == SAMPLE_RECIPES

    # recipes.source_url is varchar(255), recipes.recipe_name is varchar(200).
    assert record_from_row({"url": "https://example.com/" + "1" * 300, "name": "Суп"}) is None
    assert record_from_row({"url": "https://example.com/1", "name": "я" * 201}) is None
