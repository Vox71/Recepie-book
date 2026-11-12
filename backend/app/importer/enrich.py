"""Enrichment of imported recipes with the data of their povarenok.ru page (task 2).

The dataset importer (``app/importer/povarenok.py``) fills ``source_url``, ``name`` and
ingredients only.  This module walks the recipes that have a source URL and no parsed page
yet, downloads the page, parses it with ``app/importer/pages.py`` and writes what it found
into the structured columns and child tables:

* ``recipes.instruction`` - the same steps as numbered text (old clients keep working);
* ``recipes.cooking_time_minutes`` - only when the page publishes it (about half do);
* ``recipes.servings`` - only when the page publishes it (about four recipes in ten);
* ``recipe_steps`` - one row per step, with the photo of the step;
* ``recipe_nutrition`` - calories and macros of the whole dish and per 100 g.

Invariants, in the spirit of the dataset importer:

* **idempotent**: ``parsed_at``/``parser_version`` mark a parsed recipe, so a repeated run
  touches nothing; ``--force`` re-parses regardless of the mark;
* **offline on the second run**: the raw HTML is cached next to the service in
  ``backend/data/pages/<id>.html`` (the directory is in ``.gitignore``), so a re-parse
  costs no request and a parser change can be rolled out over the cache;
* **polite**: one request per ``--delay`` seconds, a named User-Agent, a timeout on every
  request and a stop after several blocked answers in a row - the site must not suffer
  from our import;
* **resumable**: one transaction per recipe, so a failed page does not roll back the
  recipes that were already enriched.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from psycopg2.extras import execute_values

from ..db import Database
from .pages import (
    DEFAULT_TIMEOUT_SECONDS,
    PageError,
    ParsedPage,
    fetch_recipe_page,
    parse_recipe_page,
)

logger = logging.getLogger(__name__)

# Bumped when the parser starts reading something new: rows with an older version are
# re-parsed on the next run, which is how a parser fix reaches the whole table.
PARSER_VERSION = "pages/1"
DEFAULT_DELAY_SECONDS = 1.0
DEFAULT_LIMIT = 200
# A run stops instead of hammering a site that has started to refuse us.
MAX_CONSECUTIVE_FAILURES = 3
DEFAULT_CACHE_DIR = Path("data/pages")

CANDIDATES_SQL = """
    SELECT id, source_url
    FROM recipes
    WHERE source_url IS NOT NULL
      AND (%s OR parsed_at IS NULL OR parser_version IS DISTINCT FROM %s)
    ORDER BY id
    LIMIT %s
"""

UPDATE_RECIPE_SQL = """
    UPDATE recipes
    SET instruction = COALESCE(%s, instruction),
        cooking_time_minutes = COALESCE(%s, cooking_time_minutes),
        servings = COALESCE(%s, servings),
        parsed_at = now(),
        parser_version = %s
    WHERE id = %s
"""

DELETE_STEPS_SQL = "DELETE FROM recipe_steps WHERE recipe_id = %s"
INSERT_STEPS_SQL = """
    INSERT INTO recipe_steps (recipe_id, step_number, text, image_url)
    VALUES %s
"""
UPSERT_NUTRITION_SQL = """
    INSERT INTO recipe_nutrition (
        recipe_id, calories_total, protein_total, fat_total, carbs_total,
        calories_per_100g, protein_per_100g, fat_per_100g, carbs_per_100g
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (recipe_id) DO UPDATE
    SET calories_total = EXCLUDED.calories_total,
        protein_total = EXCLUDED.protein_total,
        fat_total = EXCLUDED.fat_total,
        carbs_total = EXCLUDED.carbs_total,
        calories_per_100g = EXCLUDED.calories_per_100g,
        protein_per_100g = EXCLUDED.protein_per_100g,
        fat_per_100g = EXCLUDED.fat_per_100g,
        carbs_per_100g = EXCLUDED.carbs_per_100g,
        parsed_at = now()
"""


@dataclass
class EnrichmentStats:
    """What one run did; logged as one JSON line at the end of the command."""

    candidates: int = 0
    fetched: int = 0
    from_cache: int = 0
    updated: int = 0
    without_steps: int = 0
    without_time: int = 0
    without_servings: int = 0
    with_nutrition: int = 0
    failed: int = 0
    stopped: str | None = None

    def as_dict(self) -> dict:
        """Return the counters as a plain dict (for logging and tests)."""
        return {
            "candidates": self.candidates,
            "fetched": self.fetched,
            "from_cache": self.from_cache,
            "updated": self.updated,
            "without_steps": self.without_steps,
            "without_time": self.without_time,
            "without_servings": self.without_servings,
            "with_nutrition": self.with_nutrition,
            "failed": self.failed,
            "stopped": self.stopped,
        }


def cache_path(cache_dir: str | Path, recipe_id: int) -> Path:
    """Return the cached HTML file of a recipe."""
    return Path(cache_dir) / f"{recipe_id}.html"


def load_page(
    recipe_id: int,
    url: str,
    *,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    delay: float = DEFAULT_DELAY_SECONDS,
    refresh: bool = False,
    opener: Callable = fetch_recipe_page,
) -> tuple[str, bool]:
    """Return ``(html, from_cache)``; download only when the cache has no page.

    ``opener`` is injectable, so tests exercise the cache without the network
    (``app/importer/source.py`` uses the same trick for the Kaggle download).
    """
    path = cache_path(cache_dir, recipe_id)
    if path.is_file() and not refresh:
        return path.read_text(encoding="utf-8", errors="replace"), True

    if delay > 0:
        # Politeness: one request per delay, never a burst over the whole table.
        time.sleep(delay)
    html = opener(url, timeout=timeout)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return html, False


def enrich_recipes(
    db: Database,
    *,
    limit: int = DEFAULT_LIMIT,
    delay: float = DEFAULT_DELAY_SECONDS,
    force: bool = False,
    refresh: bool = False,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    dry_run: bool = False,
    opener: Callable = fetch_recipe_page,
) -> EnrichmentStats:
    """Enrich up to ``limit`` recipes and return the counters of the run.

    ``force`` ignores the ``parsed_at``/``parser_version`` mark (re-parse a parsed recipe),
    ``refresh`` ignores the HTML cache (download again).  ``dry_run`` parses and counts but
    writes nothing, which is what the ``--url`` mode of the CLI uses.
    """
    rows = db.fetch_all(CANDIDATES_SQL, (force, PARSER_VERSION, limit))
    stats = EnrichmentStats(candidates=len(rows))
    blocked = 0
    for row in rows:
        recipe_id = int(row["id"])
        url = str(row["source_url"])
        try:
            html, from_cache = load_page(
                recipe_id,
                url,
                cache_dir=cache_dir,
                timeout=timeout,
                delay=delay,
                refresh=refresh,
                opener=opener,
            )
            page = parse_recipe_page(html, source_url=url)
        except PageError as exc:
            stats.failed += 1
            logger.warning("Recipe %s (%s): %s", recipe_id, url, exc)
            blocked = blocked + 1 if _is_blocked(exc) else 0
            if blocked >= MAX_CONSECUTIVE_FAILURES:
                stats.stopped = f"{blocked} blocked answers in a row, the run is stopped"
                logger.error(stats.stopped)
                break
            continue

        blocked = 0
        if from_cache:
            stats.from_cache += 1
        else:
            stats.fetched += 1
        _count_page(stats, page)
        if dry_run:
            logger.info("Recipe %s: %s", recipe_id, page_summary(page))
            continue
        save_page(db, recipe_id, page)
        stats.updated += 1
        logger.info(
            "Recipe %s enriched: %s step(s), time=%s, servings=%s, nutrition=%s",
            recipe_id,
            len(page.steps),
            page.cooking_time_minutes,
            page.servings,
            page.nutrition is not None,
        )
    return stats


def save_page(db: Database, recipe_id: int, page: ParsedPage) -> None:
    """Write one parsed page to ``recipes``, ``recipe_steps`` and ``recipe_nutrition``.

    One transaction per recipe: a page that fails in the middle must not take the already
    enriched recipes with it, and the next run simply retries the failed one.
    """
    with db.cursor() as cur:
        cur.execute(
            UPDATE_RECIPE_SQL,
            (
                page.instruction_text,
                page.cooking_time_minutes,
                page.servings,
                PARSER_VERSION,
                recipe_id,
            ),
        )
        if page.steps:
            cur.execute(DELETE_STEPS_SQL, (recipe_id,))
            execute_values(
                cur,
                INSERT_STEPS_SQL,
                [
                    (recipe_id, number, text, image)
                    for number, (text, image) in enumerate(
                        zip(page.steps, page.step_images), start=1
                    )
                ],
            )
        if page.nutrition is not None:
            nutrition = page.nutrition
            cur.execute(
                UPSERT_NUTRITION_SQL,
                (
                    recipe_id,
                    nutrition.calories_total,
                    nutrition.protein_total,
                    nutrition.fat_total,
                    nutrition.carbs_total,
                    nutrition.calories_per_100g,
                    nutrition.protein_per_100g,
                    nutrition.fat_per_100g,
                    nutrition.carbs_per_100g,
                ),
            )


def page_summary(page: ParsedPage) -> dict:
    """Return a compact description of a parsed page (logs, ``--url`` mode, dry run)."""
    return {
        "url": page.source_url,
        "name": page.name,
        "steps": len(page.steps),
        "time_minutes": page.cooking_time_minutes,
        "servings": page.servings,
        "ingredients": len(page.ingredients),
        "categories": list(page.categories),
        "nutrition": (
            None
            if page.nutrition is None
            else {
                "calories_total": page.nutrition.calories_total,
                "protein_total": page.nutrition.protein_total,
                "fat_total": page.nutrition.fat_total,
                "carbs_total": page.nutrition.carbs_total,
                "calories_per_100g": page.nutrition.calories_per_100g,
            }
        ),
        "first_step": page.steps[0] if page.steps else None,
    }


def _count_page(stats: EnrichmentStats, page: ParsedPage) -> None:
    """Increase the completeness counters of the run."""
    if not page.steps:
        stats.without_steps += 1
    if page.cooking_time_minutes is None:
        stats.without_time += 1
    if page.servings is None:
        stats.without_servings += 1
    if page.nutrition is not None:
        stats.with_nutrition += 1


def _is_blocked(exc: PageError) -> bool:
    """``True`` for the answers that mean "the site does not want us right now"."""
    message = str(exc)
    return "HTTP 403" in message or "HTTP 429" in message
