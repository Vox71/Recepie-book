-- 0003: cooking time of a recipe (sprint 3, task 1 "timers in a recipe").
--
-- target state lives in app/schema.sql; this file only brings a database that was
-- created before the change to that state. app/migrate.py applies the pending
-- migrations in version order and then app/schema.sql, which is a no-op afterwards.
--
-- What changes:
--   recipes.cooking_time_minutes  new, nullable: the time a recipe takes, 1..1440
--                                 minutes.  It stays NULL for every recipe imported
--                                 from povarenok: the dataset has no time at all
--                                 (docs/sprint-2-plan.md, "Чего нет").  POST /timers
--                                 uses it as the default duration of a timer.

ALTER TABLE IF EXISTS recipes ADD COLUMN IF NOT EXISTS cooking_time_minutes integer;

-- A CHECK constraint cannot be declared with IF NOT EXISTS, so it is added once.
-- The table may be absent (app/migrate.py runs the migrations before schema.sql), and
-- to_regclass() is used instead of 'recipes'::regclass, because the cast raises.
DO $$
BEGIN
    IF to_regclass('public.recipes') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1
           FROM pg_constraint
           WHERE conname = 'recipes_cooking_time_minutes_check'
             AND conrelid = to_regclass('public.recipes')
       )
    THEN
        ALTER TABLE recipes ADD CONSTRAINT recipes_cooking_time_minutes_check
            CHECK (cooking_time_minutes BETWEEN 1 AND 1440);
    END IF;
END
$$;
