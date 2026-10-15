-- Schema of the recipe application.
-- Tables, columns and foreign keys follow docs/db_scheme.png (docs/db_plan):
--   users                    user accounts
--   recipes                  recipes
--   fridge_items             fridge contents
--   favorite_recipes         favourite recipes of a user
--   generated_recipes        history of generated recipe lists
--   user_allergy_preferences normalized allergies of a user
--   fridge_item_versions     version history of a fridge item (trigger)
--   fridge_item_audit        audit trail of fridge items (trigger)
-- The script is idempotent and executed by app.db.Database.ensure_schema().
-- Deliberate deviations from the diagram are documented in README.md.

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
    ingredients      text         NOT NULL,
    -- The diagram declares varchar(100) for the whole instruction text.
    instruction      varchar(100),
    difficulty_level varchar(50)
);

CREATE INDEX IF NOT EXISTS recipes_recipe_name_idx ON recipes (recipe_name);

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
    id        serial  PRIMARY KEY,
    user_id   integer REFERENCES users (id) ON DELETE CASCADE,
    recipe_id integer REFERENCES recipes (id) ON DELETE CASCADE,
    CONSTRAINT favorite_recipes_user_recipe_key UNIQUE (user_id, recipe_id)
);

CREATE INDEX IF NOT EXISTS favorite_recipes_user_idx ON favorite_recipes (user_id);

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
