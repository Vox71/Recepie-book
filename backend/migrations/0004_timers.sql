-- 0004: timers of a recipe (sprint 3, task 1 "timers in a recipe").
--
-- target state lives in app/schema.sql; this file only brings a database that was
-- created before the change to that state.
--
-- A timer is stored as an absolute deadline, not as a counter: ends_at is computed by
-- the database (now() + duration), so a restart of the process, a second gunicorn
-- worker or a reloaded page cannot shift it.  The client only renders
-- "ends_at - server_time" with a monotonic clock (docs/timer.md).
--
-- started_at/ends_at/closed_at are timestamptz, unlike the other timestamp columns of
-- the schema, which follow the diagram: a naive time in a timer breaks on a time zone
-- change or a DST switch.  The deviation is documented in docs/db_schema.md.

-- The table references users and recipes, so it is created only when both exist: on a
-- brand-new database the migrations run before schema.sql creates them, and there
-- schema.sql itself creates timers together with the index (see 0002 for the same
-- pattern with recipe_ingredients).
DO $$
BEGIN
    IF to_regclass('public.users') IS NOT NULL
       AND to_regclass('public.recipes') IS NOT NULL
    THEN
        CREATE TABLE IF NOT EXISTS timers (
            id               serial       PRIMARY KEY,
            user_id          integer      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            recipe_id        integer      NOT NULL REFERENCES recipes (id) ON DELETE CASCADE,
            -- What the user sees in the list ("Гречка", "Духовка"): defaults to the recipe name.
            label            varchar(100) NOT NULL,
            -- Duration in seconds, not minutes: a step like "варить 90 секунд" is a real case.
            duration_seconds integer      NOT NULL CHECK (duration_seconds BETWEEN 1 AND 86400),
            started_at       timestamptz  NOT NULL DEFAULT now(),
            ends_at          timestamptz  NOT NULL,
            -- running -> finished (ends_at passed) or cancelled (DELETE /timers/{id}).
            status           varchar(16)  NOT NULL DEFAULT 'running'
                             CHECK (status IN ('running', 'finished', 'cancelled')),
            -- When the timer stopped: ends_at for a finished one, the moment of the request
            -- for a cancelled one.  NULL while running.
            closed_at        timestamptz,
            created_at       timestamp    NOT NULL DEFAULT current_timestamp,
            CONSTRAINT timers_ends_after_start_check CHECK (ends_at > started_at)
        );

        -- The list behind GET /timers/active: one user, running timers, by ends_at.
        CREATE INDEX IF NOT EXISTS timers_user_status_idx
            ON timers (user_id, status, ends_at);
    END IF;
END
$$;
