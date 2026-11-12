"""Command line interface of the povarenok importer.

Examples:

    python -m app.importer --dataset data/povarenok --limit 1000 --batch-size 1000
    python -m app.importer --dataset tests/data/povarenok_sample.json --dry-run
    python -m app.importer --download --destination data/povarenok
    python -m app.importer --enrich --limit 200 --delay 1.0
    python -m app.importer --url https://www.povarenok.ru/recipes/show/184919/ --dry-run

``--dry-run`` parses and validates the file without touching the database, so it works
without ``DATABASE_URL``. The real run takes the connection string from the same
environment variables as the application (``app/config.py``). Progress is logged per
batch; the dataset has no personal data, so nothing sensitive reaches the log.

``--enrich`` is the second stage (sprint 3, task 2): it downloads the recipe pages of the
already imported recipes, parses them and fills the steps, time, servings and nutrition
(``app/importer/enrich.py``). ``--url`` parses the pages given on the command line and
prints what was found, which needs neither ``DATABASE_URL`` nor the dataset and is the
quickest way to see what the parser does today.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Sequence

from ..config import Settings
from ..db import Database
from ..errors import ApiError
from .enrich import (
    DEFAULT_CACHE_DIR,
    DEFAULT_DELAY_SECONDS,
    DEFAULT_LIMIT,
    enrich_recipes,
    page_summary,
)
from .pages import PageError, fetch_recipe_page, parse_recipe_page
from .povarenok import DEFAULT_BATCH_SIZE, DatasetError, find_dataset_file, import_dataset
from .source import DEFAULT_TIMEOUT_SECONDS, download_dataset

logger = logging.getLogger(__name__)

DATASET_ENV = "POVARENOK_DATASET"
DEFAULT_DESTINATION = Path("data/povarenok")
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_CONFIGURATION = 2


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser of ``python -m app.importer``."""
    parser = argparse.ArgumentParser(
        prog="python -m app.importer",
        description="Import the povarenok dataset into the recipes tables (idempotent).",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help=f"dataset file or directory (default: ${DATASET_ENV})",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        help="import at most N recipes (default: the whole file)",
    )
    parser.add_argument(
        "--batch-size",
        type=_positive_int,
        default=DEFAULT_BATCH_SIZE,
        help=f"recipes per transaction (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="parse and validate only, no database is touched",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="download the dataset from Kaggle first (needs KAGGLE_USERNAME and KAGGLE_KEY)",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=DEFAULT_DESTINATION,
        help=f"download directory (default: {DEFAULT_DESTINATION})",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"download timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="download and parse the pages of imported recipes (sprint 3, task 2)",
    )
    parser.add_argument(
        "--url",
        action="append",
        default=None,
        metavar="URL",
        help="parse this recipe page and print the result (no database, repeatable)",
    )
    parser.add_argument(
        "--pages-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=f"HTML cache of the pages (default: {DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--delay",
        type=_non_negative_float,
        default=DEFAULT_DELAY_SECONDS,
        help=f"seconds between two requests to the site (default: {DEFAULT_DELAY_SECONDS})",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="download the page again even when it is already in the cache",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="enrich again even when the recipe was parsed by this parser version",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the importer; return the process exit code."""
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    _configure_logging(settings.log_level)

    if args.url:
        return _parse_urls(args)

    database: Database | None = None
    try:
        if args.enrich:
            if not settings.database_url:
                logger.error(
                    "DATABASE_URL is not configured; --url parses pages without a database"
                )
                return EXIT_CONFIGURATION
            database = Database(settings.database_url, pool_min=1, pool_max=2)
            if settings.auto_init_schema:
                _ensure_schema(database)
            stats = enrich_recipes(
                database,
                limit=args.limit or DEFAULT_LIMIT,
                delay=args.delay,
                force=args.force,
                refresh=args.refresh,
                cache_dir=args.pages_dir,
                timeout=args.timeout,
                dry_run=args.dry_run,
            )
            logger.info(
                "Enrichment finished: %s",
                json.dumps(stats.as_dict(), ensure_ascii=False, sort_keys=True),
            )
            if stats.stopped:
                logger.error("Enrichment stopped early: %s", stats.stopped)
                return EXIT_FAILED
            return EXIT_OK

        dataset = _resolve_dataset(args)
        logger.info("Dataset: %s", dataset)
        if not args.dry_run:
            if not settings.database_url:
                logger.error(
                    "DATABASE_URL is not configured; use --dry-run to only parse the dataset"
                )
                return EXIT_CONFIGURATION
            database = Database(settings.database_url, pool_min=1, pool_max=2)
            if settings.auto_init_schema:
                _ensure_schema(database)

        stats = import_dataset(
            database,
            dataset,
            limit=args.limit,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
    except DatasetError as exc:
        logger.error("Import failed: %s", exc)
        return EXIT_FAILED
    finally:
        if database is not None:
            database.reset_pool()

    logger.info(
        "Import finished: %s", json.dumps(stats.as_dict(), ensure_ascii=False, sort_keys=True)
    )
    return EXIT_OK


def _parse_urls(args: argparse.Namespace) -> int:
    """Parse the pages given with ``--url`` and log the summary of each (no database)."""
    for url in args.url:
        try:
            page = parse_recipe_page(fetch_recipe_page(url, timeout=args.timeout), source_url=url)
        except PageError as exc:
            logger.error("%s", exc)
            return EXIT_FAILED
        logger.info("%s", json.dumps(page_summary(page), ensure_ascii=False, sort_keys=True))
        for number, step in enumerate(page.steps, start=1):
            logger.info("  %s. %s", number, step.replace("\n", " "))
        if args.delay > 0 and url != args.url[-1]:
            time.sleep(args.delay)
    return EXIT_OK


def _resolve_dataset(args: argparse.Namespace) -> Path:
    """Find the dataset file: ``--download``, ``--dataset`` or ``POVARENOK_DATASET``."""
    if args.download:
        return download_dataset(args.destination, timeout=args.timeout)

    raw = args.dataset or os.environ.get(DATASET_ENV, "")
    if not str(raw).strip():
        raise DatasetError(
            f"Dataset is not specified: pass --dataset PATH, --download or set {DATASET_ENV}"
        )
    path = Path(raw)
    if path.is_dir():
        return find_dataset_file(path)
    if not path.is_file():
        raise DatasetError(f"Dataset file not found: {path}")
    return path


def _ensure_schema(database: Database) -> None:
    """Apply ``app/schema.sql`` like the application does; a database error is fatal."""
    try:
        database.ensure_schema()
    except ApiError as exc:
        logger.warning("Schema initialization skipped: %s", exc.message)


def _configure_logging(level_name: str) -> None:
    """Apply ``LOG_LEVEL`` (``print`` is forbidden, CONTRIBUTION.md §8)."""
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger().setLevel(level)


def _positive_int(raw: str) -> int:
    """``argparse`` type: a positive integer."""
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected an integer, got '{raw}'") from exc
    if value < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value}")
    return value


def _non_negative_float(raw: str) -> float:
    """``argparse`` type: a number of seconds, zero included (no pause at all)."""
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a number, got '{raw}'") from exc
    if value < 0:
        raise argparse.ArgumentTypeError(f"expected a non-negative number, got {value}")
    return value


if __name__ == "__main__":
    sys.exit(main())
