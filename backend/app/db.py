"""PostgreSQL access layer.

Provides a small wrapper around ``psycopg2``'s thread-safe connection pool:
connections are always returned to the pool and every unit of work is a
transaction with an explicit ``rollback`` on failure (CONTRIBUTION.md §6).
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor

from .errors import DatabaseUnavailable

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class Database:
    """Thin transactional facade over a PostgreSQL connection pool."""

    def __init__(self, dsn: str, pool_min: int = 1, pool_max: int = 10) -> None:
        self._dsn = dsn
        self._pool_min = pool_min
        self._pool_max = pool_max
        self._pool: pg_pool.AbstractConnectionPool | None = None

    @property
    def is_configured(self) -> bool:
        """True when ``DATABASE_URL`` is set."""
        return bool(self._dsn)

    def _pool_or_raise(self) -> pg_pool.AbstractConnectionPool:
        if self._pool is None:
            if not self._dsn:
                raise DatabaseUnavailable("DATABASE_URL is not configured")
            try:
                self._pool = pg_pool.ThreadedConnectionPool(
                    self._pool_min, self._pool_max, dsn=self._dsn
                )
            except (psycopg2.Error, OSError) as exc:
                raise DatabaseUnavailable("Cannot connect to the database") from exc
            logger.info("Database connection pool created")
        return self._pool

    def reset_pool(self) -> None:
        """Close the cached pool so the next call establishes fresh connections."""
        pool, self._pool = self._pool, None
        if pool is not None:
            try:
                pool.closeall()
            except psycopg2.Error:
                logger.warning("Failed to close database connections cleanly")

    @staticmethod
    def _safe_rollback(connection: Any) -> None:
        try:
            connection.rollback()
        except psycopg2.Error:
            logger.warning("Rollback failed, connection will be discarded")

    @contextmanager
    def cursor(self) -> Iterator[Any]:
        """Yield a ``RealDictCursor`` and commit on success, rollback on failure."""
        pool = self._pool_or_raise()
        try:
            connection = pool.getconn()
        except pg_pool.PoolError as exc:
            raise DatabaseUnavailable("Database connection pool is exhausted") from exc

        broken = False
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cur:
                yield cur
            connection.commit()
        except psycopg2.Error as exc:
            broken = isinstance(exc, psycopg2.OperationalError)
            self._safe_rollback(connection)
            if broken:
                raise DatabaseUnavailable("Database connection was lost") from exc
            raise
        except Exception:
            self._safe_rollback(connection)
            raise
        finally:
            pool.putconn(connection, close=broken)

    def fetch_all(self, sql: str, params: Sequence[Any] | None = None) -> list[dict]:
        """Run a query and return all rows as dictionaries."""
        with self.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def fetch_one(self, sql: str, params: Sequence[Any] | None = None) -> dict | None:
        """Run a query and return the first row as a dictionary, if any."""
        with self.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row is not None else None

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> int:
        """Run a statement and return the number of affected rows."""
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def execute_many(self, sql: str, params_seq: Sequence[Sequence[Any]]) -> int:
        """Run the same statement for many parameter sets inside one transaction."""
        with self.cursor() as cur:
            cur.executemany(sql, params_seq)
            return cur.rowcount

    def health_check(self) -> bool:
        """Return True when the database answers a trivial query."""
        try:
            with self.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        except DatabaseUnavailable as exc:
            logger.warning("Database is not ready: %s", exc.message)
            return False
        except psycopg2.Error:
            logger.warning("Database health check failed", exc_info=True)
            return False
        return True

    def ensure_schema(self) -> None:
        """Apply ``schema.sql`` (idempotent, safe to run on every start)."""
        ddl = SCHEMA_PATH.read_text(encoding="utf-8")
        with self.cursor() as cur:
            cur.execute(ddl)
        logger.info("Database schema is up to date")
