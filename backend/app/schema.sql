-- Schema of the recipe application.
-- Tables, columns and foreign keys follow docs/db_scheme.png (docs/db_plan) plus the
-- extensions that the imported povarenok dataset requires (docs/db_schema.md):
--   users                    user accounts
--   recipes                  recipes (manual ones and imported ones)
--   recipe_ingredients       normalized ingredient lists of a recipe
--   recipe_steps             step-by-step instructions parsed from the source page
--   recipe_nutrition         calories/macros of a recipe parsed from the source page
--   fridge_items             fridge contents
--   favorite_recipes         favourite recipes of a user
--   timers                   running timers of a recipe (sprint 3, task 1)
--   generated_recipes        history of generated recipe lists
--   user_allergy_preferences normalized allergies of a user
--   fridge_item_versions     version history of a fridge item (trigger)
--   fridge_item_audit        audit trail of fridge items (trigger)
-- The script is idempotent and executed by app.db.Database.ensure_schema().
-- Deliberate deviations from the diagram are documented in README.md and
-- docs/db_schema.md; migrations that bring an existing database to this shape live
-- in backend/migrations (applied by app/migrate.py).

CREATE TABLE IF NOT EXISTS users (
    id          serial       PRIMARY KEY,
    username    varchar(80)  NOT NULL,
    -- Werkzeug scrypt hash: 162 characters, therefore varchar(200) instead of
    -- the varchar(120) of the diagram (see README.md).
    password    varchar(200) NOT NULL,
    email       varchar(120) NOT NULL,
    -- Comma separated terms ("nuts, milk"): the text form of what
    -- user_allergy_preferences stores row by row.
    allergies   text,
    preferences text,
    CONSTRAINT users_username_key UNIQUE (username),
    CONSTRAINT users_email_key UNIQUE (email)
);

-- openapi.yaml treats the e-mail as case-insensitive, the diagram has no index.
CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_key ON users (lower(email));

CREATE TABLE IF NOT EXISTS recipes (
    id               serial       PRIMARY KEY,
    recipe_name      varchar(200) NOT NULL,
    -- Denormalized ingredient text ("pasta, tomato, cheese"): the input of the ML
    -- module and what openapi.yaml returns as "ingredients".
    ingredients      text         NOT NULL,
    -- The diagram declares varchar(100) for the whole instruction text. It is text
    -- because an instruction does not fit into 100 characters, and every recipe of
    -- the imported povarenok dataset has no instruction at all (NULL).
    instruction      text,
    difficulty_level varchar(50),
    -- Natural key of an imported recipe (its url on povarenok.ru). Manual recipes
    -- have no source, so the column stays NULL for them; PostgreSQL allows any
    -- number of NULLs in a UNIQUE constraint, which is what the parser needs to
    -- stay idempotent (INSERT ... ON CONFLICT (source_url) DO NOTHING).
    source_url       varchar(255),
    -- How long the recipe takes, in minutes: the default duration of a timer
    -- (POST /timers, docs/timer.md).  NULL for every imported recipe - the
    -- povarenok dataset has no time at all - so the client asks for the duration
    -- explicitly for them.
    cooking_time_minutes integer   CHECK (cooking_time_minutes BETWEEN 1 AND 1440),
    -- How many portions the recipe yields (the page publishes it for about half of the
    -- recipes).  It is what user story 6 recalculates ingredients by.
    servings         integer      CHECK (servings BETWEEN 1 AND 100),
    -- Enrichment by the page parser (sprint 3, task 2): parsed_at IS NULL means "the
    -- recipe page was never parsed"; parser_version lets a new parser re-run by version.
    parsed_at        timestamptz,
    parser_version   varchar(20),
    created_at       timestamp    NOT NULL DEFAULT current_timestamp,
    -- Maintained by the recipes_updated_at_trigger below, so every writer
    -- (API, parser, psql shell) leaves the same value.
    updated_at       timestamp    NOT NULL DEFAULT current_timestamp,
    CONSTRAINT recipes_source_url_key UNIQUE (source_url)
);

CREATE INDEX IF NOT EXISTS recipes_recipe_name_idx ON recipes (recipe_name);

-- Ingredients of a recipe, one row per ingredient. The povarenok dataset stores
-- them as a dict {"Яйцо куриное": "5 шт", ...}: the key becomes ingredient_name,
-- the value quantity_text. recipes.ingredients keeps the flattened text, so the
-- existing endpoints and the ML module do not depend on this table.
CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id              serial       PRIMARY KEY,
    recipe_id       integer      NOT NULL REFERENCES recipes (id) ON DELETE CASCADE,
    ingredient_name varchar(200) NOT NULL,
    -- The amount exactly as written in the source ("150 г", "1 щепот."); NULL when
    -- the source gives no amount. Parsing it into a number is out of scope.
    quantity_text   varchar(100),
    -- Position in the source list, so the order can be restored.
    sort_order      integer      NOT NULL DEFAULT 0,
    -- One ingredient once per recipe; the index also serves recipe_id lookups.
    CONSTRAINT recipe_ingredients_recipe_name_key UNIQUE (recipe_id, ingredient_name)
);

-- Ingredient lookups in the other direction: "which recipes contain milk?" is the
-- query behind allergen filtering (docs/db_schema.md).
CREATE INDEX IF NOT EXISTS recipe_ingredients_name_idx ON recipe_ingredients (ingredient_name);

-- Steps of a recipe, one row per step, as parsed from the source page (sprint 3, task 2).
-- recipes.instruction keeps the same steps as numbered text, so older clients keep
-- working; the rows below are what user story 6 ("ingredients on every step") and the
-- planned step timers build on.  A manual recipe has no rows here.
CREATE TABLE IF NOT EXISTS recipe_steps (
    id          serial       PRIMARY KEY,
    recipe_id   integer      NOT NULL REFERENCES recipes (id) ON DELETE CASCADE,
    -- Position in the source list (1-based), restored as-is.
    step_number integer      NOT NULL CHECK (step_number > 0),
    -- Plain text of one step; a <br> of the source becomes a newline.
    text        text         NOT NULL,
    -- Photo of the step; NULL when the author added none.
    image_url   varchar(255),
    -- One number once per recipe; the index also serves recipe_id lookups.
    CONSTRAINT recipe_steps_recipe_number_key UNIQUE (recipe_id, step_number)
);

CREATE INDEX IF NOT EXISTS recipe_steps_recipe_idx ON recipe_steps (recipe_id, step_number);

-- Nutrition of a recipe, at most one row per recipe, parsed from the source page.
-- The page publishes two groups ("Готового блюда" and "100 г блюда"); per-serving values
-- are derivable from recipes.servings, so they are not stored (docs/povarenok-pages.md).
CREATE TABLE IF NOT EXISTS recipe_nutrition (
    recipe_id          integer        PRIMARY KEY
                       REFERENCES recipes (id) ON DELETE CASCADE,
    calories_total     numeric(10, 2) CHECK (calories_total >= 0),
    protein_total      numeric(10, 2) CHECK (protein_total >= 0),
    fat_total          numeric(10, 2) CHECK (fat_total >= 0),
    carbs_total        numeric(10, 2) CHECK (carbs_total >= 0),
    calories_per_100g  numeric(10, 2) CHECK (calories_per_100g >= 0),
    protein_per_100g   numeric(10, 2) CHECK (protein_per_100g >= 0),
    fat_per_100g       numeric(10, 2) CHECK (fat_per_100g >= 0),
    carbs_per_100g     numeric(10, 2) CHECK (carbs_per_100g >= 0),
    -- Where the numbers come from: 'povarenok' today.
    source             varchar(32)    NOT NULL DEFAULT 'povarenok',
    parsed_at          timestamptz    NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fridge_items (
    item_id         serial       PRIMARY KEY,
    user_id         integer      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    product_name    varchar(100) NOT NULL,
    expiration_date date         NOT NULL,
    quantity        integer      NOT NULL DEFAULT 1 CHECK (quantity > 0),
    last_added      timestamp    NOT NULL DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS fridge_items_user_expiration_idx
    ON fridge_items (user_id, expiration_date);

CREATE INDEX IF NOT EXISTS fridge_items_expiration_idx ON fridge_items (expiration_date);

CREATE TABLE IF NOT EXISTS favorite_recipes (
    id         serial    PRIMARY KEY,
    user_id    integer   REFERENCES users (id) ON DELETE CASCADE,
    recipe_id  integer   REFERENCES recipes (id) ON DELETE CASCADE,
    -- The favourites list is returned newest first, so the moment of adding matters.
    created_at timestamp NOT NULL DEFAULT current_timestamp,
    CONSTRAINT favorite_recipes_user_recipe_key UNIQUE (user_id, recipe_id)
);

-- The index is created only when the column exists: on a database created before the
-- change ensure_schema() cannot add favorite_recipes.created_at, and a CREATE INDEX that
-- mentions the missing column fails even with IF NOT EXISTS (the name is checked after
-- the statement is parsed and the column is resolved).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'favorite_recipes'
          AND column_name = 'created_at'
    ) THEN
        CREATE INDEX IF NOT EXISTS favorite_recipes_user_idx
            ON favorite_recipes (user_id, created_at);
    END IF;
END
$$;

-- Timers of a recipe (sprint 3, task 1). A timer is an absolute deadline, not a
-- counter: ends_at is computed by the database, so a restart, a second worker or a
-- reloaded page cannot shift it; the client only renders ends_at - server_time with a
-- monotonic clock (docs/timer.md).  started_at/ends_at/closed_at are timestamptz,
-- unlike the other timestamp columns, which follow the diagram: a naive time breaks on
-- a time zone change or a DST switch (docs/db_schema.md).
CREATE TABLE IF NOT EXISTS timers (
    id               serial       PRIMARY KEY,
    user_id          integer      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    recipe_id        integer      NOT NULL REFERENCES recipes (id) ON DELETE CASCADE,
    -- What the user sees in the list ("Гречка", "Духовка"): defaults to the recipe name.
    label            varchar(100) NOT NULL,
    -- Duration in seconds, not minutes: "варить 90 секунд" is a real case.
    duration_seconds integer      NOT NULL CHECK (duration_seconds BETWEEN 1 AND 86400),
    started_at       timestamptz  NOT NULL DEFAULT now(),
    ends_at          timestamptz  NOT NULL,
    -- running -> finished (ends_at passed) or cancelled (DELETE /timers/{id}).
    status           varchar(16)  NOT NULL DEFAULT 'running'
                     CHECK (status IN ('running', 'finished', 'cancelled')),
    -- When the timer stopped: ends_at for a finished one, the moment of the request for
    -- a cancelled one; NULL while running.
    closed_at        timestamptz,
    created_at       timestamp    NOT NULL DEFAULT current_timestamp,
    CONSTRAINT timers_ends_after_start_check CHECK (ends_at > started_at)
);

-- The list behind GET /timers/active: one user, running timers, ordered by ends_at.
CREATE INDEX IF NOT EXISTS timers_user_status_idx ON timers (user_id, status, ends_at);

CREATE TABLE IF NOT EXISTS generated_recipes (
    id           serial    PRIMARY KEY,
    user_id      integer   REFERENCES users (id) ON DELETE CASCADE,
    recipes_id   integer   REFERENCES recipes (id) ON DELETE CASCADE,
    generated_on timestamp NOT NULL DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS generated_recipes_user_idx
    ON generated_recipes (user_id, generated_on);

CREATE TABLE IF NOT EXISTS user_allergy_preferences (
    id           serial       PRIMARY KEY,
    user_id      integer      REFERENCES users (id) ON DELETE CASCADE,
    allergy_name varchar(100) NOT NULL
);

CREATE INDEX IF NOT EXISTS user_allergy_preferences_user_idx
    ON user_allergy_preferences (user_id);

CREATE TABLE IF NOT EXISTS fridge_item_versions (
    id              serial      PRIMARY KEY,
    -- ON DELETE SET NULL keeps the history of a removed item; the diagram
    -- declares no rule and NO ACTION would break DELETE /delete_expired_products.
    fridge_items_id integer     REFERENCES fridge_items (item_id) ON DELETE SET NULL,
    version         integer     NOT NULL DEFAULT 1,
    product_name    varchar(100),
    expiration_date date,
    quantity        integer,
    updated_at      timestamp   NOT NULL DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS fridge_item_versions_item_idx
    ON fridge_item_versions (fridge_items_id, version);

CREATE TABLE IF NOT EXISTS fridge_item_audit (
    id              serial      PRIMARY KEY,
    action_type     varchar(50) NOT NULL,
    user_id         integer     REFERENCES users (id) ON DELETE CASCADE,
    product_name    varchar(100),
    expiration_date date,
    quantity        integer,
    action_time     timestamp   NOT NULL DEFAULT current_timestamp,
    old_values      jsonb,
    new_value       jsonb
);

CREATE INDEX IF NOT EXISTS fridge_item_audit_user_time_idx
    ON fridge_item_audit (user_id, action_time);

-- Both histories are maintained by the database itself, so they stay correct for
-- every writer (the API, the worker, the psql shell) and not only for the
-- application code.
CREATE OR REPLACE FUNCTION fridge_items_log_version() RETURNS trigger AS $$
BEGIN
    INSERT INTO fridge_item_versions
        (fridge_items_id, version, product_name, expiration_date, quantity)
    VALUES (
        NEW.item_id,
        COALESCE(
            (SELECT MAX(version) FROM fridge_item_versions WHERE fridge_items_id = NEW.item_id),
            0
        ) + 1,
        NEW.product_name,
        NEW.expiration_date,
        NEW.quantity
    );
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fridge_items_log_audit() RETURNS trigger AS $$
BEGIN
    INSERT INTO fridge_item_audit
        (action_type, user_id, product_name, expiration_date, quantity, old_values, new_value)
    VALUES (
        TG_OP,
        COALESCE(NEW.user_id, OLD.user_id),
        COALESCE(NEW.product_name, OLD.product_name),
        COALESCE(NEW.expiration_date, OLD.expiration_date),
        COALESCE(NEW.quantity, OLD.quantity),
        CASE WHEN TG_OP <> 'INSERT' THEN to_jsonb(OLD) END,
        CASE WHEN TG_OP <> 'DELETE' THEN to_jsonb(NEW) END
    );
    RETURN NULL;
EXCEPTION
    -- Deleting a user cascades into fridge_items; the user row is already gone
    -- when this trigger runs, so the audit row cannot reference it. The entry is
    -- skipped instead of failing the DELETE.
    WHEN foreign_key_violation THEN
        RAISE WARNING 'fridge_item_audit entry skipped, user % is being deleted', OLD.user_id;
        RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS fridge_items_version_trigger ON fridge_items;
CREATE TRIGGER fridge_items_version_trigger
    AFTER INSERT OR UPDATE OF product_name, expiration_date, quantity ON fridge_items
    FOR EACH ROW EXECUTE FUNCTION fridge_items_log_version();

DROP TRIGGER IF EXISTS fridge_items_audit_trigger ON fridge_items;
CREATE TRIGGER fridge_items_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON fridge_items
    FOR EACH ROW EXECUTE FUNCTION fridge_items_log_audit();

-- recipes.updated_at is a property of the row, not of the request: the trigger
-- updates it on every UPDATE, no matter which writer (API, parser, psql) ran it.
CREATE OR REPLACE FUNCTION recipes_touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := current_timestamp;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- The trigger is created only when the column exists. On a database created before the
-- change CREATE TABLE IF NOT EXISTS is a no-op, so ensure_schema() alone cannot add
-- updated_at; a trigger that writes a missing field would break every UPDATE until
-- python -m app.migrate adds the column.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'recipes' AND column_name = 'updated_at'
    ) THEN
        DROP TRIGGER IF EXISTS recipes_updated_at_trigger ON recipes;
        CREATE TRIGGER recipes_updated_at_trigger
            BEFORE UPDATE ON recipes
            FOR EACH ROW EXECUTE FUNCTION recipes_touch_updated_at();
    END IF;
END
$$;
