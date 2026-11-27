-- 0006: normalized amounts of imported ingredients.
--
-- quantity_text keeps the source spelling ("250 мл", "3 шт", "1 кг"); the two columns
-- below store the parsed number and its canonical unit.  Mass is stored in grams and
-- volume in millilitres.  The columns are nullable because a source may contain only
-- "по вкусу" or a range, which must not be turned into an invented number.

DO $$
BEGIN
    IF to_regclass('public.recipe_ingredients') IS NOT NULL THEN
        ALTER TABLE recipe_ingredients
            ADD COLUMN IF NOT EXISTS quantity_value numeric(12, 3);
        ALTER TABLE recipe_ingredients
            ADD COLUMN IF NOT EXISTS quantity_unit varchar(20);

        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'recipe_ingredients_quantity_value_check'
        ) THEN
            ALTER TABLE recipe_ingredients
                ADD CONSTRAINT recipe_ingredients_quantity_value_check
                CHECK (quantity_value IS NULL OR quantity_value >= 0);
        END IF;
    END IF;
END
$$;
