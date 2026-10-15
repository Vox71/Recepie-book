"""Versioned SQL migrations for existing databases.

``app/schema.sql`` is the single source of truth for the shape of a **fresh**
database (:meth:`app.db.Database.ensure_schema`). The files in ``backend/migrations``
describe how a database that already exists reaches the same shape
(CONTRIBUTION.md §6), and this runner applies them exactly once, recording every
version in the ``schema_migrations`` table.

Usage::

    python -m app.migrate           # apply pending migrations, then schema.sql

Migrations run in version order, each one in its own transaction. Afterwards
``schema.sql`` is applied again, so the final state never depends on how old the
database was.
"""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv

from .config import Settings
from .db import Database

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATIONS_TABLE = "schema_migrations"
CREATE_MIGRATIONS_TABLE = f"""
    CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
        version    text        PRIMARY KEY,
        applied_at timestamptz NOT NULL DEFAULT now()
    )
"""

logger = logging.getLogger(__name__)


def migration_files(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    """Return the migration files of ``directory`` in application order."""
    return sorted(directory.glob("*.sql"))


def applied_versions(db: Database) -> set[str]:
    """Return the versions already recorded in ``schema_migrations``."""
    rows = db.fetch_all(f"SELECT version FROM {MIGRATIONS_TABLE}")
    return {str(row["version"]) for row in rows}


def apply_migrations(db: Database, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply every pending migration and return the versions that were applied."""
    db.execute(CREATE_MIGRATIONS_TABLE)
    already_applied = applied_versions(db)
    applied: list[str] = []
    for path in migration_files(directory):
        if path.stem in already_applied:
            continue
        with db.cursor() as cur:
            cur.execute(path.read_text(encoding="utf-8"))
            cur.execute(f"INSERT INTO {MIGRATIONS_TABLE} (version) VALUES (%s)", (path.stem,))
        logger.info("Migration %s applied", path.stem)
        applied.append(path.stem)
    return applied


def migrate(database_url: str, *, pool_min: int = 1, pool_max: int = 10) -> list[str]:
    """Apply the migrations and ``schema.sql`` to ``database_url``."""
    db = Database(database_url, pool_min, pool_max)
    try:
        applied = apply_migrations(db)
        db.ensure_schema()
    finally:
        db.reset_pool()
    return applied


def main() -> None:
    """Command line entry point (``python -m app.migrate``)."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    load_dotenv()
    settings = Settings.from_env()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not configured")
    applied = migrate(
        settings.database_url, pool_min=settings.db_pool_min, pool_max=settings.db_pool_max
    )
    print("Applied migrations:", ", ".join(applied) if applied else "none")


if __name__ == "__main__":
    main()
