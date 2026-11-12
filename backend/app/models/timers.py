"""SQL access layer for the ``timers`` table (parameterised queries only).

A timer is an absolute deadline, never a counter: ``ends_at`` is computed by PostgreSQL
in the same statement that inserts the row, and ``remaining_seconds``/``server_time``
are computed by the same clock when the row is read.  That is what makes the countdown
independent of the process, of a second gunicorn worker and of the clock of the device
(docs/timer.md).

``ends_at`` is a ``timestamptz`` (see ``app/schema.sql``): a naive timestamp would break
on a time zone change or a DST switch.
"""

from __future__ import annotations

from ..db import Database

TIMER_COLUMNS = "id, recipe_id, label, duration_seconds, started_at, ends_at, status, closed_at"
# The reference pair for the client: ends_at (when the timer rings) and server_time
# (what the server thinks "now" is).  Both come from one statement, so the difference
# "ends_at - server_time" is exact and needs no clock of the device at all.
TIMER_READ_COLUMNS = f"""{TIMER_COLUMNS},
    GREATEST(0, CEIL(EXTRACT(EPOCH FROM ends_at - now())))::int AS remaining_seconds,
    now() AS server_time"""


def count_active(db: Database, user_id: int) -> int:
    """Return how many timers of ``user_id`` are still running."""
    sql = """
        SELECT count(*) AS active
        FROM timers
        WHERE user_id = %s AND status = 'running' AND ends_at > now()
    """
    row = db.fetch_one(sql, (user_id,))
    return int(row["active"]) if row else 0


def create(db: Database, user_id: int, recipe_id: int, label: str, duration_seconds: int) -> dict:
    """Insert a running timer and return the row the API answers with."""
    sql = f"""
        INSERT INTO timers (user_id, recipe_id, label, duration_seconds, ends_at)
        VALUES (%s, %s, %s, %s, now() + make_interval(secs => %s))
        RETURNING {TIMER_READ_COLUMNS}
    """
    return db.fetch_one(sql, (user_id, recipe_id, label, duration_seconds, duration_seconds))


def close_expired(db: Database, user_id: int) -> int:
    """Mark the timers whose deadline has passed as ``finished``; return their count.

    Called before the list of active timers is read, so no background worker is needed
    to keep the table honest.  ``closed_at`` is set to ``ends_at`` - the moment the
    timer should have stopped - and not to ``now()``, which is when it was noticed.
    """
    sql = """
        UPDATE timers
        SET status = 'finished', closed_at = ends_at
        WHERE user_id = %s AND status = 'running' AND ends_at <= now()
    """
    return db.execute(sql, (user_id,))


def list_active(db: Database, user_id: int, *, limit: int) -> list[dict]:
    """Return the running timers of ``user_id``, the one ending first on top."""
    sql = f"""
        SELECT {TIMER_READ_COLUMNS}
        FROM timers
        WHERE user_id = %s AND status = 'running' AND ends_at > now()
        ORDER BY ends_at, id
        LIMIT %s
    """
    return db.fetch_all(sql, (user_id, limit))


def server_now(db: Database):
    """Return ``now()`` of the database — the reference clock of every timer."""
    return db.fetch_one("SELECT now() AS server_time")["server_time"]


def cancel(db: Database, timer_id: int, user_id: int) -> bool:
    """Stop a running timer of ``user_id``; ``False`` when there is nothing to stop.

    A timer of another user, an unknown id and an already finished timer all give
    ``False``: the answer is the same 404, so it does not disclose whether the row
    exists (the same rule as ``favorite_recipes``).
    """
    sql = """
        UPDATE timers
        SET status = 'cancelled', closed_at = now()
        WHERE id = %s AND user_id = %s AND status = 'running'
    """
    return db.execute(sql, (timer_id, user_id)) > 0
