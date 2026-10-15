-- Schema of the recipe application.
-- Tables are derived from the models declared in openapi.yaml:
--   users        -> RegisterRequest / LoginRequest / UserPreferencesRequest
--   recipes      -> components.schemas.Recipe
--   fridge_items -> components.schemas.FridgeItem
-- The script is idempotent and executed by app.db.Database.ensure_schema().

CREATE TABLE IF NOT EXISTS users (
    id            bigserial PRIMARY KEY,
    username      text        NOT NULL,
    email         text        NOT NULL,
    password_hash text        NOT NULL,
    -- Stored "as is": /register accepts a string, /user_preferences sends a list.
    allergies     jsonb       NOT NULL DEFAULT '[]'::jsonb,
    preferences   jsonb       NOT NULL DEFAULT '[]'::jsonb,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_username_key UNIQUE (username)
);

CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_key ON users (lower(email));

CREATE TABLE IF NOT EXISTS recipes (
    id               bigserial   PRIMARY KEY,
    name             text        NOT NULL,
    ingredients      text        NOT NULL,
    instructions     text        NOT NULL,
    cuisine_type     text,
    difficulty_level text,
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS recipes_cuisine_type_idx ON recipes (cuisine_type);

CREATE TABLE IF NOT EXISTS fridge_items (
    id              bigserial   PRIMARY KEY,
    user_id         bigint      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    product_name    text        NOT NULL,
    expiration_date date        NOT NULL,
    quantity        numeric     NOT NULL CHECK (quantity > 0),
    last_added      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fridge_items_user_expiration_idx
    ON fridge_items (user_id, expiration_date);

CREATE INDEX IF NOT EXISTS fridge_items_expiration_idx ON fridge_items (expiration_date);
