"""Reader and importer of the povarenok dataset.

The Kaggle dataset ``rogozinushka/povarenok-recipes`` is a table of three columns:
``url``, ``name`` and ``ingredients`` (a mapping ``{ingredient: quantity}``). It has no
instructions, servings or difficulty, so an imported recipe keeps ``instruction`` and
``difficulty_level`` NULL and is recognised by ``recipes.source_url``
(docs/db_schema.md).

Two invariants of this module:

- **idempotent**: ``source_url`` is the natural key of an imported recipe, the insert
  is ``ON CONFLICT (source_url) DO NOTHING``, so a repeated run of the same file adds
  nothing. Each batch is one transaction: a failed run keeps the batches it committed
  and the next run continues where it stopped;
- **streaming**: rows are read one by one (``csv`` from the standard library,
  ``pyarrow`` for parquet), so memory does not grow with the size of the file.

The module knows nothing about Flask: the CLI (``app/importer/cli.py``) opens a
``Database`` and passes it in, tests use a temporary file and the same functions.
"""

from __future__ import annotations

import ast
import csv
import json
import logging
import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from psycopg2.extras import execute_values

from ..db import Database

logger = logging.getLogger(__name__)

# Limits of the target columns (app/schema.sql): an over-long value would be rejected
# by PostgreSQL in the middle of a batch, so such rows are skipped and counted instead.
MAX_URL_LENGTH = 255  # recipes.source_url
MAX_NAME_LENGTH = 200  # recipes.recipe_name
MAX_INGREDIENT_LENGTH = 200  # recipe_ingredients.ingredient_name
MAX_QUANTITY_LENGTH = 100  # recipe_ingredients.quantity_text

DEFAULT_BATCH_SIZE = 1000
READ_BATCH_SIZE = 1000
# recipes.ingredients is NOT NULL, so a recipe without ingredients still needs text.
NO_INGREDIENTS_TEXT = "ингредиенты не указаны"

SUPPORTED_SUFFIXES = frozenset({".parquet", ".csv", ".json", ".jsonl", ".ndjson"})
# The CSV export of the dataset is written by pandas, so a recipe without ingredients
# (or without an amount) arrives as an empty cell, "nan" or "None" rather than a dict.
MISSING_VALUES = frozenset({"", "nan", "none", "null", "nat", "<na>"})

INSERT_RECIPES_SQL = """
    INSERT INTO recipes (source_url, recipe_name, ingredients, instruction, difficulty_level)
    VALUES %s
    ON CONFLICT (source_url) DO NOTHING
    RETURNING id, source_url
"""
RECIPE_TEMPLATE = "(%s, %s, %s, NULL, NULL)"

INSERT_INGREDIENTS_SQL = """
    INSERT INTO recipe_ingredients (recipe_id, ingredient_name, quantity_text, sort_order)
    VALUES %s
    ON CONFLICT (recipe_id, ingredient_name) DO NOTHING
    RETURNING id
"""
INGREDIENT_TEMPLATE = "(%s, %s, %s, %s)"


class DatasetError(RuntimeError):
    """The dataset cannot be read: wrong format, missing file, missing dependency."""


@dataclass(frozen=True)
class Ingredient:
    """One line of the source ingredient mapping."""

    name: str
    quantity: str | None


@dataclass(frozen=True)
class RecipeRecord:
    """A dataset row that passed validation, ready for the database."""

    source_url: str
    name: str
    ingredients: tuple[Ingredient, ...] = field(default_factory=tuple)

    @property
    def ingredients_text(self) -> str:
        """Flattened ingredient list stored in ``recipes.ingredients``."""
        return render_ingredients(self.ingredients)


@dataclass
class ImportStats:
    """What a single ``import_dataset`` run did (also the content of the dry run)."""

    dry_run: bool = False
    rows_read: int = 0
    records_skipped: int = 0
    recipes_parsed: int = 0
    recipes_inserted: int = 0
    recipes_duplicated: int = 0
    ingredients_parsed: int = 0
    ingredients_inserted: int = 0

    def as_dict(self) -> dict[str, int | bool]:
        """Return the counters as a plain dictionary for logging and tests."""
        return {
            "dry_run": self.dry_run,
            "rows_read": self.rows_read,
            "records_skipped": self.records_skipped,
            "recipes_parsed": self.recipes_parsed,
            "recipes_inserted": self.recipes_inserted,
            "recipes_duplicated": self.recipes_duplicated,
            "ingredients_parsed": self.ingredients_parsed,
            "ingredients_inserted": self.ingredients_inserted,
        }


def normalize_text(value: Any) -> str:
    """Collapse whitespace (including non-breaking spaces) and trim the result."""
    if value is None:
        return ""
    return " ".join(str(value).replace("\u00a0", " ").split())


def normalize_ingredient_name(value: Any) -> str:
    """Normalize an ingredient name and drop trailing punctuation."""
    return normalize_text(value).strip(" .,;:")


def parse_ingredients(raw: Any) -> tuple[Ingredient, ...]:
    """Turn the ``ingredients`` column into normalized ``(name, quantity)`` pairs.

    The dataset stores a mapping, but a CSV export holds it as text and an older dump
    may hold a list, therefore all three shapes are accepted:

    - mapping ``{"Мука": "300 г"}`` — the shape of the dataset;
    - text ``'{"Мука": "300 г"}'`` or ``"Мука: 300 г; Соль: щепотка"``;
    - list of ``"Мука: 300 г"`` lines or mappings.

    Names are compared case-insensitively: one ingredient appears once per recipe,
    which is also the unique constraint of ``recipe_ingredients``.
    """
    if raw is None:
        return ()
    if isinstance(raw, float) and math.isnan(raw):
        return ()
    if isinstance(raw, str):
        text = raw.strip()
        if text.casefold() in MISSING_VALUES:
            return ()
        decoded = _decode_literal(text)
        if decoded is not None:
            return parse_ingredients(decoded)
        return _ingredients_from_pairs(_split_lines(text))
    if isinstance(raw, Mapping):
        pairs: list[tuple[Any, Any]] = list(raw.items())
    elif isinstance(raw, (list, tuple)):
        pairs = []
        for item in raw:
            if isinstance(item, Mapping):
                pairs.extend(item.items())
            elif isinstance(item, str):
                pairs.append(_split_line(item))
            else:
                pairs.append((item, None))
    else:
        return ()
    return _ingredients_from_pairs(pairs)


def render_ingredients(ingredients: Sequence[Ingredient]) -> str:
    """Render ingredients as the comma separated text of ``recipes.ingredients``."""
    if not ingredients:
        return NO_INGREDIENTS_TEXT
    parts = []
    for ingredient in ingredients:
        if ingredient.quantity:
            parts.append(f"{ingredient.name} — {ingredient.quantity}")
        else:
            parts.append(ingredient.name)
    return ", ".join(parts)


def record_from_row(row: Mapping[str, Any]) -> RecipeRecord | None:
    """Build a record from a raw dataset row; ``None`` when the row is unusable."""
    source_url = normalize_text(row.get("url"))
    name = normalize_text(row.get("name"))
    if not source_url.startswith(("http://", "https://")):
        return None
    if len(source_url) > MAX_URL_LENGTH or not name or len(name) > MAX_NAME_LENGTH:
        return None
    return RecipeRecord(
        source_url=source_url,
        name=name,
        ingredients=parse_ingredients(row.get("ingredients")),
    )


def iter_rows(path: str | Path, *, batch_size: int = READ_BATCH_SIZE) -> Iterator[dict]:
    """Yield raw dataset rows, choosing the reader by the file suffix."""
    dataset_path = Path(path)
    suffix = dataset_path.suffix.lower()
    if suffix == ".parquet":
        yield from _iter_parquet(dataset_path, batch_size)
    elif suffix == ".csv":
        yield from _iter_csv(dataset_path)
    elif suffix in {".jsonl", ".ndjson"}:
        yield from _iter_json_lines(dataset_path)
    elif suffix == ".json":
        yield from _iter_json_array(dataset_path)
    else:
        raise DatasetError(
            f"Unsupported dataset format '{suffix or dataset_path.name}', "
            f"expected one of: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )


def find_dataset_file(directory: str | Path) -> Path:
    """Return the single dataset file of ``directory`` (parquet, csv or json)."""
    directory_path = Path(directory)
    candidates = sorted(
        path for path in directory_path.iterdir() if path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if not candidates:
        raise DatasetError(
            f"No dataset file ({', '.join(sorted(SUPPORTED_SUFFIXES))}) in {directory}"
        )
    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise DatasetError(f"Several dataset files in {directory}: {names}; pass --dataset FILE")
    return candidates[0]


def import_dataset(
    db: Database | None,
    path: str | Path,
    *,
    limit: int | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
) -> ImportStats:
    """Import the dataset at ``path`` and return the counters of the run.

    ``limit`` caps the number of parsed recipes (not raw rows); ``dry_run`` parses and
    validates the file without touching the database, so ``db`` may be ``None``.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    if not dry_run and db is None:
        raise ValueError("db is required unless dry_run is set")

    stats = ImportStats(dry_run=dry_run)
    batch: list[RecipeRecord] = []
    for row in iter_rows(path, batch_size=batch_size):
        stats.rows_read += 1
        record = record_from_row(row)
        if record is None:
            stats.records_skipped += 1
            logger.warning("Skipped dataset row %s: no usable url or name", stats.rows_read)
            continue

        stats.recipes_parsed += 1
        stats.ingredients_parsed += len(record.ingredients)
        if dry_run:
            if limit is not None and stats.recipes_parsed >= limit:
                break
            continue

        batch.append(record)
        if len(batch) >= batch_size:
            _insert_batch(db, batch, stats)
            batch = []
        if limit is not None and stats.recipes_parsed >= limit:
            break
    if batch:
        _insert_batch(db, batch, stats)
    return stats


def _insert_batch(db: Database, batch: Sequence[RecipeRecord], stats: ImportStats) -> None:
    """Insert one batch of recipes with their ingredients inside one transaction."""
    recipes = [(record.source_url, record.name, record.ingredients_text) for record in batch]
    with db.cursor() as cur:
        execute_values(
            cur,
            INSERT_RECIPES_SQL,
            recipes,
            template=RECIPE_TEMPLATE,
            page_size=len(recipes),
        )
        inserted = cur.fetchall()
        stats.recipes_inserted += len(inserted)
        stats.recipes_duplicated += len(batch) - len(inserted)

        if not inserted:
            logger.info("Batch of %s recipe(s) already imported", len(batch))
            return

        by_source = {record.source_url: record for record in batch}
        ingredient_values = [
            (int(row["id"]), ingredient.name, ingredient.quantity, position)
            for row in inserted
            for position, ingredient in enumerate(by_source[row["source_url"]].ingredients)
        ]
        if ingredient_values:
            execute_values(
                cur,
                INSERT_INGREDIENTS_SQL,
                ingredient_values,
                template=INGREDIENT_TEMPLATE,
                page_size=len(ingredient_values),
            )
            stats.ingredients_inserted += len(cur.fetchall())
    logger.info(
        "Batch imported: %s recipe(s), %s duplicate(s), %s ingredient(s)",
        len(inserted),
        len(batch) - len(inserted),
        stats.ingredients_inserted,
    )


def _ingredients_from_pairs(pairs: Sequence[tuple[Any, Any]]) -> tuple[Ingredient, ...]:
    """Normalize, deduplicate and bound the pairs of one recipe."""
    ingredients: list[Ingredient] = []
    seen: set[str] = set()
    for raw_name, raw_quantity in pairs:
        name = normalize_ingredient_name(raw_name)
        if not name or len(name) > MAX_INGREDIENT_LENGTH or name.casefold() in MISSING_VALUES:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        ingredients.append(Ingredient(name=name, quantity=_normalize_quantity(raw_quantity)))
    return tuple(ingredients)


def _normalize_quantity(value: Any) -> str | None:
    """Turn an amount into ``quantity_text``; ``None`` when the source gives no amount."""
    if isinstance(value, float) and math.isnan(value):
        return None
    quantity = normalize_text(value)[:MAX_QUANTITY_LENGTH]
    return quantity or None


def _split_lines(text: str) -> list[tuple[Any, Any]]:
    """Split ``"Мука: 300 г; Соль: щепотка"`` style text into pairs."""
    parts: list[str] = []
    for line in text.splitlines():
        parts.extend(line.split(";"))
    return [_split_line(part) for part in parts if part.strip()]


def _split_line(line: str) -> tuple[Any, Any]:
    """Split ``"Мука: 300 г"`` into ``("Мука", "300 г")``."""
    name, separator, quantity = line.partition(":")
    return (name, quantity) if separator else (line, None)


def _decode_literal(text: str) -> Any:
    """Decode a JSON or Python literal (the CSV export holds ``str(dict)``).

    The dataset's CSV is written by pandas, so ``ingredients`` looks like
    ``{'Яйцо куриное': '5 шт'}`` — a Python literal, not JSON. ``ast.literal_eval``
    accepts only literals, therefore it cannot execute anything from the file.
    """
    if not text.startswith(("{", "[")):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None


def _iter_json_array(path: Path) -> Iterator[dict]:
    """Read a JSON array of rows (small files, including the test sample)."""
    with path.open(encoding="utf-8") as source:
        payload = json.load(source)
    if not isinstance(payload, list):
        raise DatasetError(f"{path} must contain a JSON array of rows")
    for row in payload:
        if not isinstance(row, dict):
            raise DatasetError(f"{path} must contain JSON objects, got {type(row).__name__}")
        yield row


def _iter_json_lines(path: Path) -> Iterator[dict]:
    """Read one JSON object per line."""
    with path.open(encoding="utf-8") as source:
        for number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetError(f"{path}:{number} is not valid JSON") from exc
            if not isinstance(row, dict):
                raise DatasetError(f"{path}:{number} is not a JSON object")
            yield row


def _iter_csv(path: Path) -> Iterator[dict]:
    """Read a CSV export of the dataset row by row."""
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        missing = {"url", "name", "ingredients"} - set(reader.fieldnames or [])
        if missing:
            raise DatasetError(f"{path} has no column(s): {', '.join(sorted(missing))}")
        yield from reader


def _iter_parquet(path: Path, batch_size: int) -> Iterator[dict]:
    """Read a parquet file in batches (``pyarrow`` is an optional dependency)."""
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise DatasetError(
            "Reading parquet needs pyarrow: pip install -r requirements-ml.txt"
        ) from exc
    reader = parquet.ParquetFile(path)
    for batch in reader.iter_batches(batch_size=batch_size):
        yield from batch.to_pylist()
