# Схема базы данных

Документ описывает фактическую структуру PostgreSQL-базы проекта: 9 таблиц, их колонки, типы,
ограничения, индексы и триггеры. Источник истины — [`backend/app/schema.sql`](../backend/app/schema.sql)
(целевое состояние для новой базы) и [`backend/migrations`](../backend/migrations) (то же состояние
для уже существующей). Документ сверен с ними и с тестом
[`backend/tests/test_database.py`](../backend/tests/test_database.py), который проверяет каждую
таблицу, колонку и правило.

Исходные материалы: ER-диаграмма [`docs/db_scheme.png`](db_scheme.png) и её текстовое описание
[`docs/db_plan`](db_plan). Всё, что добавлено сверх диаграммы, перечислено в разделе
[«Расширения под импорт датасета»](#расширения-под-импорт-датасета).

## Содержание

- [Как применить и как посмотреть схему](#как-применить-и-как-посмотреть-схему)
- [Обзор таблиц и связей](#обзор-таблиц-и-связей)
- [Таблицы](#таблицы)
- [Индексы и уникальные ограничения](#индексы-и-уникальные-ограничения)
- [Триггеры и функции](#триггеры-и-функции)
- [Расширения под импорт датасета](#расширения-под-импорт-датасета)
- [Осознанные отличия от диаграммы](#осознанные-отличия-от-диаграммы)
- [Миграции](#миграции)
- [Как схема проверяется тестами](#как-схема-проверяется-тестами)
- [Что осталось за рамками](#что-осталось-за-рамками)

## Как применить и как посмотреть схему

```bash
cd backend
python -m app.migrate     # неприменённые миграции, затем app/schema.sql (идемпотентно)
```

`app/db.py::Database.ensure_schema()` выполняет только `app/schema.sql`, поэтому он создаёт
**новую** базу, но не добавляет колонки в существующую. Для существующей базы всегда
`python -m app.migrate`: он применяет файлы из `backend/migrations` по порядку и записывает
версии в таблицу `schema_migrations`.

Посмотреть фактическое состояние:

```bash
psql "$DATABASE_URL" -c '\dt'          # список таблиц
psql "$DATABASE_URL" -c '\d+ recipes'  # колонки, индексы, внешние ключи, триггеры
psql "$DATABASE_URL" -c 'SELECT * FROM schema_migrations ORDER BY version'
```

## Обзор таблиц и связей

| Таблица | Назначение | Связи |
|---|---|---|
| `users` | учётные записи: логин, scrypt-хэш пароля, e-mail, аллергии и предпочтения в текстовом виде | — |
| `recipes` | рецепты: ручные (через API) и импортированные из датасета | — |
| `recipe_ingredients` | нормализованный список ингредиентов рецепта, по строке на ингредиент | `recipes.id` (CASCADE) |
| `fridge_items` | содержимое холодильника | `users.id` (CASCADE) |
| `favorite_recipes` | избранные рецепты пользователя | `users.id`, `recipes.id` (CASCADE) |
| `generated_recipes` | что именно выдавали пользователю (`/suggest_recipes`, `/recommend_recipes`) | `users.id`, `recipes.id` (CASCADE) |
| `user_allergy_preferences` | аллергии пользователя, по строке на термин | `users.id` (CASCADE) |
| `fridge_item_versions` | история версий продукта (наполняется триггером) | `fridge_items.item_id` (SET NULL) |
| `fridge_item_audit` | аудит действий с продуктами: `old_values`/`new_value` в JSONB | `users.id` (CASCADE) |

```mermaid
erDiagram
    users ||--o{ fridge_items : "владеет"
    users ||--o{ favorite_recipes : "добавляет"
    users ||--o{ generated_recipes : "получает"
    users ||--o{ user_allergy_preferences : "указывает"
    users ||--o{ fridge_item_audit : "действует"
    recipes ||--o{ favorite_recipes : "попадает в избранное"
    recipes ||--o{ generated_recipes : "был выдан"
    recipes ||--o{ recipe_ingredients : "состоит из"
    fridge_items ||--o{ fridge_item_versions : "версии"
    fridge_items ||--o{ fridge_item_audit : "аудит"
```

Связи «многие ко многим» между пользователем и рецептом выражены двумя таблицами: `favorite_recipes`
(что пользователь сохранил) и `generated_recipes` (что ему показали). `recipe_ingredients` —
третья связь «рецепт → ингредиент», нужная импорту датасета и фильтрации по аллергенам.

## Таблицы

Обозначения: `PK` — первичный ключ, `FK` — внешний ключ, `NN` — `NOT NULL`, `U` — уникальное
ограничение. Значения по умолчанию указаны явно.

### `users`

| Колонка | Тип | Ограничения | Комментарий |
|---|---|---|---|
| `id` | `integer` | PK, `serial` | |
| `username` | `character varying(80)` | NN, U `users_username_key` | |
| `password` | `character varying(200)` | NN | scrypt-хэш werkzeug — 162 символа, поэтому 200, а не 120 из диаграммы |
| `email` | `character varying(120)` | NN, U `users_email_key` | плюс уникальный индекс по `lower(email)`: контракт считает e-mail регистронезависимым |
| `allergies` | `text` | — | термины через запятую; построчная форма — `user_allergy_preferences` |
| `preferences` | `text` | — | вкусовые предпочтения в свободной форме |

### `recipes`

| Колонка | Тип | Ограничения | Комментарий |
|---|---|---|---|
| `id` | `integer` | PK, `serial` | |
| `recipe_name` | `character varying(200)` | NN | |
| `ingredients` | `text` | NN | денормализованный текст («pasta, tomato, cheese»): вход ML-модуля и поле `ingredients` в API |
| `instruction` | `text` | — | `NULL` для импортированных рецептов: в датасете инструкций нет |
| `difficulty_level` | `character varying(50)` | — | `NULL` для импортированных рецептов |
| `source_url` | `character varying(255)` | U `recipes_source_url_key` | естественный ключ импортированного рецепта (url на povarenok.ru); у ручных рецептов `NULL`, и PostgreSQL разрешает любое число `NULL` |
| `created_at` | `timestamp` | NN, по умолчанию `current_timestamp` | |
| `updated_at` | `timestamp` | NN, по умолчанию `current_timestamp` | обновляется триггером `recipes_updated_at_trigger` при каждом `UPDATE` |

### `recipe_ingredients`

| Колонка | Тип | Ограничения | Комментарий |
|---|---|---|---|
| `id` | `integer` | PK, `serial` | |
| `recipe_id` | `integer` | NN, FK → `recipes.id` ON DELETE CASCADE | |
| `ingredient_name` | `character varying(200)` | NN, U `recipe_ingredients_recipe_name_key` вместе с `recipe_id` | один ингредиент один раз на рецепт |
| `quantity_text` | `character varying(100)` | — | количество как в источнике («150 г», «1 щепот.»); `NULL`, если его нет |
| `sort_order` | `integer` | NN, по умолчанию `0` | порядок ингредиентов в источнике |

Ингредиенты хранятся и в `recipes.ingredients` (текстом), и здесь (по строкам). Дублирование
осознанное: существующие адреса и ML-модуль работают с текстом и не зависят от новой таблицы, а
фильтрация по аллергенам и будущий поиск по продуктам — с нормализованными строками.

### `fridge_items`

| Колонка | Тип | Ограничения | Комментарий |
|---|---|---|---|
| `item_id` | `integer` | PK, `serial` | имя ключа отличается от остальных таблиц — так в диаграмме |
| `user_id` | `integer` | NN, FK → `users.id` ON DELETE CASCADE | |
| `product_name` | `character varying(100)` | NN | |
| `expiration_date` | `date` | NN | |
| `quantity` | `integer` | NN, по умолчанию `1`, CHECK (`quantity > 0`) | |
| `last_added` | `timestamp` | NN, по умолчанию `current_timestamp` | |

### `favorite_recipes`

| Колонка | Тип | Ограничения | Комментарий |
|---|---|---|---|
| `id` | `integer` | PK, `serial` | |
| `user_id` | `integer` | FK → `users.id` ON DELETE CASCADE | |
| `recipe_id` | `integer` | FK → `recipes.id` ON DELETE CASCADE | |
| `created_at` | `timestamp` | NN, по умолчанию `current_timestamp` | список избранного отдаётся от новых к старым |

Уникальность пары задаёт `favorite_recipes_user_recipe_key`, поэтому повторное добавление того же
рецепта — идемпотентная операция (`ON CONFLICT DO NOTHING`), а не ошибка.

### `generated_recipes`

| Колонка | Тип | Ограничения | Комментарий |
|---|---|---|---|
| `id` | `integer` | PK, `serial` | |
| `user_id` | `integer` | FK → `users.id` ON DELETE CASCADE | |
| `recipes_id` | `integer` | FK → `recipes.id` ON DELETE CASCADE | имя колонки с суффиксом `_id` — так в диаграмме |
| `generated_on` | `timestamp` | NN, по умолчанию `current_timestamp` | |

### `user_allergy_preferences`

| Колонка | Тип | Ограничения | Комментарий |
|---|---|---|---|
| `id` | `integer` | PK, `serial` | |
| `user_id` | `integer` | FK → `users.id` ON DELETE CASCADE | |
| `allergy_name` | `character varying(100)` | NN | один термин на строку; дубли исключает приложение при перезаписи |

### `fridge_item_versions`

| Колонка | Тип | Ограничения | Комментарий |
|---|---|---|---|
| `id` | `integer` | PK, `serial` | |
| `fridge_items_id` | `integer` | FK → `fridge_items.item_id` ON DELETE SET NULL | история продукта сохраняется после его удаления |
| `version` | `integer` | NN, по умолчанию `1` | номер версии, считает триггер |
| `product_name` | `character varying(100)` | — | снимок значений |
| `expiration_date` | `date` | — | снимок значений |
| `quantity` | `integer` | — | снимок значений |
| `updated_at` | `timestamp` | NN, по умолчанию `current_timestamp` | |

### `fridge_item_audit`

| Колонка | Тип | Ограничения | Комментарий |
|---|---|---|---|
| `id` | `integer` | PK, `serial` | |
| `action_type` | `character varying(50)` | NN | `INSERT` / `UPDATE` / `DELETE` (значение `TG_OP`) |
| `user_id` | `integer` | FK → `users.id` ON DELETE CASCADE | |
| `product_name` | `character varying(100)` | — | |
| `expiration_date` | `date` | — | |
| `quantity` | `integer` | — | |
| `action_time` | `timestamp` | NN, по умолчанию `current_timestamp` | |
| `old_values` | `jsonb` | — | строка до изменения (для `INSERT` — `NULL`) |
| `new_value` | `jsonb` | — | строка после изменения (для `DELETE` — `NULL`) |

## Индексы и уникальные ограничения

| Имя | Таблица | Колонки | Тип | Зачем |
|---|---|---|---|---|
| `users_username_key` | `users` | `username` | UNIQUE | логин уникален |
| `users_email_key` | `users` | `email` | UNIQUE | e-mail уникален |
| `users_email_lower_key` | `users` | `lower(email)` | UNIQUE INDEX | контракт считает e-mail регистронезависимым |
| `recipes_recipe_name_idx` | `recipes` | `recipe_name` | INDEX | сортировка и поиск по названию |
| `recipes_source_url_key` | `recipes` | `source_url` | UNIQUE | идемпотентный импорт (`ON CONFLICT (source_url)`) |
| `recipe_ingredients_recipe_name_key` | `recipe_ingredients` | `recipe_id`, `ingredient_name` | UNIQUE | один ингредиент один раз; префикс `recipe_id` обслуживает выборку по рецепту |
| `recipe_ingredients_name_idx` | `recipe_ingredients` | `ingredient_name` | INDEX | «в каких рецептах есть молоко» — фильтрация по аллергенам |
| `fridge_items_user_expiration_idx` | `fridge_items` | `user_id`, `expiration_date` | INDEX | срок годности в разрезе пользователя |
| `fridge_items_expiration_idx` | `fridge_items` | `expiration_date` | INDEX | уведомления воркера по всем пользователям |
| `favorite_recipes_user_recipe_key` | `favorite_recipes` | `user_id`, `recipe_id` | UNIQUE | нет дублей в избранном |
| `favorite_recipes_user_idx` | `favorite_recipes` | `user_id`, `created_at` | INDEX | список избранного от новых к старым |
| `generated_recipes_user_idx` | `generated_recipes` | `user_id`, `generated_on` | INDEX | история выдач пользователя |
| `user_allergy_preferences_user_idx` | `user_allergy_preferences` | `user_id` | INDEX | чтение профиля аллергий |
| `fridge_item_versions_item_idx` | `fridge_item_versions` | `fridge_items_id`, `version` | INDEX | максимум версии в триггере |
| `fridge_item_audit_user_time_idx` | `fridge_item_audit` | `user_id`, `action_time` | INDEX | аудит по пользователю и времени |

## Триггеры и функции

| Объект | Таблица | Событие | Что делает |
|---|---|---|---|
| `fridge_items_version_trigger` → `fridge_items_log_version()` | `fridge_items` | `AFTER INSERT OR UPDATE OF product_name, expiration_date, quantity` | пишет новую строку в `fridge_item_versions` с номером `MAX(version) + 1` |
| `fridge_items_audit_trigger` → `fridge_items_log_audit()` | `fridge_items` | `AFTER INSERT OR UPDATE OR DELETE` | пишет строку в `fridge_item_audit` с `old_values`/`new_value`; при удалении пользователя запись пропускается с `WARNING`, чтобы каскад не падал на внешнем ключе |
| `recipes_updated_at_trigger` → `recipes_touch_updated_at()` | `recipes` | `BEFORE UPDATE` | присваивает `updated_at = current_timestamp` |

Истории холодильника ведутся базой, а не кодом приложения: они остаются верными для любого
писателя (API, воркер, `psql`). По той же причине `recipes.updated_at` обновляет триггер, а не
сервисный слой: значение нельзя забыть выставить.

## Расширения под импорт датасета

Данные берутся из датасета Kaggle `rogozinushka/povarenok-recipes` (~147 000 рецептов, выгрузка
2021-06-16, лицензия не указана). Поля датасета: `url`, `name`, `ingredients` — словарь
`{ингредиент: количество}`. Отсюда три расширения диаграммы:

1. **`recipes.source_url`** — `url` датасета стал естественным ключом. Повторный запуск парсера
   не создаёт дублей (`INSERT ... ON CONFLICT (source_url) DO NOTHING`), а ручные рецепты живут
   рядом с импортированными, потому что у них `source_url IS NULL`.
2. **`recipe_ingredients`** — словарь ингредиентов разложен по строкам: ключ → `ingredient_name`,
   значение → `quantity_text`, порядок → `sort_order`. Текстовая колонка `recipes.ingredients`
   заполняется склейкой ключей, поэтому существующие адреса, ML-модуль и тесты не меняются.
3. **`recipes.created_at` / `recipes.updated_at`** — без них нельзя ни упорядочить импорт, ни
   понять, когда рецепт правили; для импортированных рецептов это единственная метка времени.

Следствия, которые важно помнить при работе с импортом:

- `instruction` и `difficulty_level` у импортированных рецептов — `NULL`. Контракт API это пока
  не разрешает (`openapi.yaml` объявляет их обязательными в ответе), поэтому синхронизация
  контракта вынесена в отдельную задачу спринта;
- `recipes.ingredients` — `NOT NULL`, поэтому парсер обязан записать непустую склейку
  ингредиентов, даже если словарь пуст (тогда — название рецепта);
- объём (147 тыс. рецептов, порядка 1–1,5 млн строк ингредиентов) требует пакетной вставки:
  батчи по 1–5 тыс. строк в одной транзакции;
- данные датасета не коммитятся в репозиторий: в git хранится только скрипт загрузки, а в тестах
  используется маленький синтетический сэмпл.

## Осознанные отличия от диаграммы

- `users.password varchar(200)` вместо `varchar(120)`: scrypt-хэш werkzeug занимает 162 символа;
- `fridge_item_versions.fridge_items_id ... ON DELETE SET NULL`: с `NO ACTION` падал бы
  `DELETE /delete_expired_products`, а история продукта терялась бы;
- `fridge_items.quantity integer NOT NULL DEFAULT 1 CHECK (quantity > 0)`: количество не может быть
  нулевым или дробным;
- уникальный индекс `users_email_lower_key` по `lower(email)`;
- `NOT NULL DEFAULT current_timestamp` у всех timestamp-колонок (`last_added`, `action_time`,
  `updated_at`, `generated_on`, `created_at`), `NOT NULL` у `fridge_item_versions.version`;
- `recipes.instruction` объявлена `text` и nullable: инструкция не помещается в 100 символов, а у
  импортированных рецептов её нет вовсе (валидация API пока ограничивает 100 символами — см.
  задачу синхронизации контракта);
- `recipes.ingredients` названа правильно: в `docs/db_plan` слово написано с опечаткой
  («igredients»), а `openapi.yaml` и SQL используют `ingredients`;
- `cuisine_type` в схеме отсутствует: колонка удалена из диаграммы и из контракта.

## Миграции

| Версия | Файл | Что делает |
|---|---|---|
| `0001` | `0001_db_scheme_rework.sql` | удаляет три легаси-таблицы, но только пока в базе нет `favorite_recipes`: база, уже приведённая к `schema.sql`, не теряет данные, если `schema_migrations` ещё пуста |
| `0002` | `0002_recipe_ingredients.sql` | `instruction` → `text`; `source_url`, `created_at`, `updated_at` в `recipes`; таблица `recipe_ingredients`; `favorite_recipes.created_at`; триггер `recipes_updated_at_trigger` |

Правила:

- `schema.sql` — целевое состояние **новой** базы, миграция — путь для **существующей**;
- `schema.sql` использует `CREATE TABLE IF NOT EXISTS` и на существующей базе колонки не добавит,
  поэтому после изменения схемы всегда запускается `python -m app.migrate`;
- каждая миграция идемпотентна (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`, `DO $$`
  вокруг `ADD CONSTRAINT`), потому что повторный запуск не должен ломать базу;
- применённые версии видны в `schema_migrations`.

## Как схема проверяется тестами

`backend/tests/test_database.py` — 11 кейсов, нужен PostgreSQL:

| Кейс | Что проверяет |
|---|---|
| `test_tables_columns_and_primary_keys_match_the_diagram` | ровно 9 таблиц, тип и длина каждой колонки, первичные ключи, отсутствие `cuisine_type` |
| `test_foreign_keys_and_the_email_index_match_the_diagram` | все внешние ключи с правилом `ON DELETE`, уникальный индекс `lower(email)` |
| `test_triggers_and_functions_of_the_fridge_history_exist` | оба триггера и обе функции истории холодильника |
| `test_database_constraints_are_enforced` | `CHECK`, `NOT NULL`, `UNIQUE` (включая регистронезависимый e-mail) |
| `test_fridge_history_records_the_insert_and_the_update` | версии и аудит после `INSERT`/`UPDATE` |
| `test_fridge_history_survives_the_delete_of_a_product_and_of_a_user` | `SET NULL` в версиях и пропуск аудита при каскадном удалении |
| `test_favorite_recipes_are_unique_and_cascade` | уникальность пары, каскад при удалении рецепта |
| `test_generated_recipes_keep_what_was_offered` | запись выдачи, пустая выдача, каскад |
| `test_recipe_ingredients_are_unique_and_cascade` | один ингредиент один раз, `NULL` в количестве, каскад, внешний ключ |
| `test_imported_recipes_are_unique_by_source_url` | уникальность `source_url`, несколько `NULL`, `ON CONFLICT DO NOTHING` |
| `test_recipe_timestamps_and_the_text_instruction_are_maintained_by_the_database` | `created_at`/`updated_at` и триггер, инструкция длиннее 100 символов, `NULL` у импортированного рецепта |

Запуск только этого файла:

```bash
cd backend
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:55432/recipes_test \
  python -m pytest tests/test_database.py -v
```

## Что осталось за рамками

- Справочник ингредиентов (`ingredients`) и единиц измерения: сейчас ингредиент — строка,
  количество — текст. Для точного поиска по продуктам и граммовок нужна отдельная нормализация.
- Шаги приготовления как отдельная сущность (`recipe_steps`): в датасете их нет, поэтому таблица
  не заводится «на будущее».
- Аллергены как справочник в БД (`allergens`, связь с ингредиентами): на первом этапе словарь
  живёт в коде ML-модуля (`app/ml/allergens.py`, задача про аллергии и непереносимости).
- Векторный поиск (`pgvector`): расширение потребует другого образа PostgreSQL, поэтому
  эмбеддинги хранятся в файле-артефакте модели, а не в базе.




