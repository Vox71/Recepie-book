-- 0005: enrichment of a recipe from its povarenok.ru page (sprint 3, task 2).
--
-- The Kaggle dataset behind recipes.source_url has only url/name/ingredients.  The page
-- itself carries schema.org microdata: steps, cooking time, servings and nutrition.  This
-- migration adds the target columns and the two child tables that keep that data
-- structured (docs/povarenok-pages.md).
--
-- Everything is guarded: on a brand-new database the migrations run before schema.sql
-- creates recipes, and there schema.sql itself creates the same shape (see 0002/0004).

DO $$
BEGIN
    IF to_regclass('public.recipes') IS NOT NULL THEN
        -- Steps of a manual recipe stay in instruction; the parser writes both: the
        -- numbered text (old clients) and the rows below (docs/user_story.md, story 6).
        ALTER TABLE recipes ADD COLUMN IF NOT EXISTS servings integer;
        -- Which run enriched the row: parsed_at IS NULL means "no page parsed yet",
        -- parser_version lets a new parser re-run over old rows (--force by version).
        ALTER TABLE recipes ADD COLUMN IF NOT EXISTS parsed_at timestamptz;
        ALTER TABLE recipes ADD COLUMN IF NOT EXISTS parser_version varchar(20);

        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'recipes_servings_check'
        ) THEN
            ALTER TABLE recipes
                ADD CONSTRAINT recipes_servings_check CHECK (servings BETWEEN 1 AND 100);
        END IF;

        CREATE TABLE IF NOT EXISTS recipe_steps (
            id          serial       PRIMARY KEY,
            recipe_id   integer      NOT NULL REFERENCES recipes (id) ON DELETE CASCADE,
            -- The order of the source list (1-based), restored as-is.
            step_number integer      NOT NULL CHECK (step_number > 0),
            -- Text of one step as plain text; <br> of the source becomes a newline.
            text        text         NOT NULL,
            -- Photo of the step; NULL when the author added none.
            image_url   varchar(255),
            CONSTRAINT recipe_steps_recipe_number_key UNIQUE (recipe_id, step_number)
        );

        CREATE INDEX IF NOT EXISTS recipe_steps_recipe_idx
            ON recipe_steps (recipe_id, step_number);

        -- One row per recipe (1:1).  The page publishes two groups: the whole dish and
        -- 100 g of it; per serving is derivable from servings, so it is not stored.
        CREATE TABLE IF NOT EXISTS recipe_nutrition (
            recipe_id          integer       PRIMARY KEY
                               REFERENCES recipes (id) ON DELETE CASCADE,
            calories_total     numeric(10, 2) CHECK (calories_total >= 0),
            protein_total      numeric(10, 2) CHECK (protein_total >= 0),
            fat_total          numeric(10, 2) CHECK (fat_total >= 0),
            carbs_total        numeric(10, 2) CHECK (carbs_total >= 0),
            calories_per_100g  numeric(10, 2) CHECK (calories_per_100g >= 0),
            protein_per_100g   numeric(10, 2) CHECK (protein_per_100g >= 0),
            fat_per_100g       numeric(10, 2) CHECK (fat_per_100g >= 0),
            carbs_per_100g     numeric(10, 2) CHECK (carbs_per_100g >= 0),
            -- Where the numbers come from: 'povarenok' today, a future parser may add.
            source             varchar(32)  NOT NULL DEFAULT 'povarenok',
            parsed_at          timestamptz  NOT NULL DEFAULT now()
        );
    END IF;
END
$$;
