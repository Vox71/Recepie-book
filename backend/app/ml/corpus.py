"""Corpus of the v1 model (sprint 2, tasks 6.0 and 6.2): where the recipe texts come from.

Both commands of the model work on the same object - a list of ``RecipeEntry``:

* ``python -m app.ml.model`` fits the IDF weights on it and saves the artifact;
* ``python -m app.ml.evaluate`` measures the ranking on it and compares the model with
  the bag-of-lemmas baseline.

There are three sources, and they all end up in the same shape:

* a dataset file (``--sample``): JSON/JSONL/CSV/parquet in the povarenok format, read by
  ``app.importer.povarenok`` - so the sample of the test suite and the real dataset are
  parsed by the same code;
* the database (``--from-db``): ``recipes`` plus the normalized ``recipe_ingredients``,
  which is the same source the running service uses at request time;
* plain rows (``from_rows``): used by the database path and by the tests.

Ingredient names are *not* lemmatized here: the model and the evaluator lemmatize texts
themselves with ``app.ml.preprocessing``, so the corpus keeps the original spelling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from ..importer.povarenok import NO_INGREDIENTS_TEXT, DatasetError, iter_rows, parse_ingredients

logger = logging.getLogger(__name__)


class CorpusError(ValueError):
    """The corpus cannot be read or contains no recipe with an ingredient list."""


DEFAULT_CORPUS = Path("tests/data/recommendation_sample.json")
"""Sample of the test suite: it is committed, so both commands run without a database."""

DEFAULT_DATABASE_LIMIT = 20000
"""Recipes taken from the database by default: enough for stable IDF, fast to evaluate."""


@dataclass(frozen=True)
class RecipeEntry:
    """One recipe of the corpus: a name (for the report) and its ingredient names."""

    name: str
    ingredients: tuple[str, ...]

    @property
    def text(self) -> str:
        """The ingredient list as one string - the input of the vectorizer."""
        return ", ".join(self.ingredients)


def load_corpus(path: str | Path) -> list[RecipeEntry]:
    """Read a dataset file (json, jsonl, csv or parquet) into ``RecipeEntry`` items.

    Rows without a usable ingredient list are skipped and counted in the log: the real
    dataset has such rows, and they cannot teach the model anything.
    """
    entries: list[RecipeEntry] = []
    skipped = 0
    try:
        for row in iter_rows(path):
            ingredients = tuple(
                ingredient.name for ingredient in parse_ingredients(row.get("ingredients"))
            )
            if not ingredients:
                skipped += 1
                continue
            entries.append(RecipeEntry(name=str(row.get("name") or ""), ingredients=ingredients))
    except (OSError, DatasetError) as exc:
        raise CorpusError(f"cannot read the corpus {path}: {exc}") from exc
    if not entries:
        raise CorpusError(f"{path}: no recipe with an ingredient list")
    if skipped:
        logger.info("%s: %s row(s) without ingredients skipped", path, skipped)
    return entries


def from_rows(
    rows: Sequence[Mapping[str, object]],
    ingredient_names: Mapping[int, Sequence[str]] | None = None,
    *,
    limit: int | None = None,
) -> list[RecipeEntry]:
    """Build the corpus from ``recipes`` rows and the ``recipe_ingredients`` map.

    ``recipe_ingredients`` is the source of truth, exactly as in the allergen filter; a
    recipe created through ``POST /recipes`` has no rows there, so its ``ingredients``
    text is split by the same parser the importer uses.
    """
    entries: list[RecipeEntry] = []
    for row in rows:
        if limit is not None and len(entries) >= limit:
            break
        names = _ingredient_names(row, ingredient_names)
        if not names:
            continue
        entries.append(RecipeEntry(name=str(row.get("recipe_name") or ""), ingredients=names))
    return entries


def from_database(dsn: str, *, limit: int | None = DEFAULT_DATABASE_LIMIT) -> list[RecipeEntry]:
    """Read the corpus from PostgreSQL (``DATABASE_URL``) - the production source.

    The connection is closed before returning: both commands are one-off jobs, not part
    of the request path.
    """
    from ..db import Database  # imported here: the module stays importable without a DSN
    from ..models import recipes as recipes_model

    database = Database(dsn, pool_max=2)
    try:
        rows = recipes_model.list_recipes_for_model(database, limit=limit)
        ids = [int(row["id"]) for row in rows]
        entries = from_rows(rows, recipes_model.list_ingredient_names(database, ids))
    finally:
        database.reset_pool()
    logger.info("Corpus from the database: %s recipe(s)", len(entries))
    return entries


def _ingredient_names(
    row: Mapping[str, object], ingredient_names: Mapping[int, Sequence[str]] | None
) -> tuple[str, ...]:
    """Ingredient names of one recipe: normalized rows first, the text column second.

    An imported recipe without ingredients carries the placeholder text of the importer
    (``NO_INGREDIENTS_TEXT``); it is not a product, so such a recipe is left out instead of
    teaching the model a lemma that no dish has.
    """
    row_id = row.get("id")
    if row_id is not None and ingredient_names is not None:
        names = ingredient_names.get(int(row_id))
        if names:
            return tuple(str(name) for name in names)
    text = str(row.get("ingredients") or "")
    if text.strip() == NO_INGREDIENTS_TEXT:
        return ()
    return tuple(ingredient.name for ingredient in parse_ingredients(text))
