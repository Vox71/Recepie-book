-- 0001: rework of the three table schema (users, recipes, fridge_items) into the
-- eight table schema declared in docs/db_scheme.png (see docs/db_plan).
--
-- The rework happened while the database was still empty (the product is not
-- released yet), therefore the legacy tables are dropped instead of being
-- migrated column by column. The target state itself lives in app/schema.sql:
-- app/migrate.py applies this file first and then app/schema.sql, so a database
-- that still has the old tables ends up with exactly the new eight tables.

DROP TABLE IF EXISTS fridge_items CASCADE;
DROP TABLE IF EXISTS recipes CASCADE;
DROP TABLE IF EXISTS users CASCADE;
