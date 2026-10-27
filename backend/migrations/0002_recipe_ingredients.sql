-- 0002: the recipe structure required by the imported povarenok dataset
-- (docs/db_schema.md, task "schema of the imported recipes").
--
-- target state lives in app/schema.sql; this file only brings a database that was
-- created before the change to that state. app/migrate.py applies the pending
-- migrations in version order and then app/schema.sql, which is a no-op afterwards.
--
-- What changes:
--   recipes.instruction            varchar(100) -> text (imported recipes have none at all)
--   recipes.source_url             new, UNIQUE: the natural key of an imported recipe
--   recipes.created_at/updated_at  new (updated_at is maintained by a trigger)
--   recipe_ingredients             new table, one row per ingredient of a recipe
--   favorite_recipes.created_at    new (the favourites list is ordered by it)

ALTER TABLE IF EXISTS recipes ALTER COLUMN instruction TYPE text;

ALTER TABLE IF EXISTS recipes ADD COLUMN IF NOT EXISTS source_url varchar(255);
ALTER TABLE IF EXISTS recipes
    ADD COLUMN IF NOT EXISTS created_at timestamp NOT NULL DEFAULT current_timestamp;
ALTER TABLE IF EXISTS recipes
    ADD COLUMN IF NOT EXISTS updated_at timestamp NOT NULL DEFAULT current_timestamp;

-- A UNIQUE constraint cannot be declared with IF NOT EXISTS, so it is added once.
-- The table may not exist yet: app/migrate.py runs the migrations before schema.sql,
-- and on a brand-new database recipes is created by schema.sql afterwards. to_regclass()
-- is used instead of 'recipes'::regclass, because the cast raises when the table is absent.
DO $$
BEGIN
    IF to_regclass('public.recipes') IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'recipes_source_url_key'
              AND conrelid = to_regclass('public.recipes')
        ) THEN
            ALTER TABLE recipes ADD CONSTRAINT recipes_source_url_key UNIQUE (source_url);
        END IF;
    END IF;
END
$$;

-- The foreign key makes this statement depend on recipes, so it runs only when the
-- table already exists; a brand-new database gets it from schema.sql afterwards.
DO $$
BEGIN
    IF to_regclass('public.recipes') IS NOT NULL THEN
        CREATE TABLE IF NOT EXISTS recipe_ingredients (
            id              serial       PRIMARY KEY,
            recipe_id       integer      NOT NULL REFERENCES recipes (id) ON DELETE CASCADE,
            ingredient_name varchar(200) NOT NULL,
            quantity_text   varchar(100),
            sort_order      integer      NOT NULL DEFAULT 0,
            CONSTRAINT recipe_ingredients_recipe_name_key UNIQUE (recipe_id, ingredient_name)
        );

        CREATE INDEX IF NOT EXISTS recipe_ingredients_name_idx
            ON recipe_ingredients (ingredient_name);
    END IF;
END
$$;

ALTER TABLE IF EXISTS favorite_recipes
    ADD COLUMN IF NOT EXISTS created_at timestamp NOT NULL DEFAULT current_timestamp;

-- The old index was (user_id); the favourites list is now ordered by created_at.
DROP INDEX IF EXISTS favorite_recipes_user_idx;
CREATE INDEX IF NOT EXISTS favorite_recipes_user_idx ON favorite_recipes (user_id, created_at);

CREATE OR REPLACE FUNCTION recipes_touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := current_timestamp;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- A trigger needs its table, and DROP TRIGGER ... ON <missing table> raises even with
-- IF EXISTS, so both statements are skipped until recipes exists (schema.sql on a new
-- database creates the table together with the trigger).
DO $$
BEGIN
    IF to_regclass('public.recipes') IS NOT NULL THEN
        DROP TRIGGER IF EXISTS recipes_updated_at_trigger ON recipes;
        CREATE TRIGGER recipes_updated_at_trigger
            BEFORE UPDATE ON recipes
            FOR EACH ROW EXECUTE FUNCTION recipes_touch_updated_at();
    END IF;
END
$$;
