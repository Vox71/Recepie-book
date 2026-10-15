# Recepie-book
Учебный групповой проект

## Бэкенд (Flask + PostgreSQL)

Реализация полностью соответствует контракту `openapi.yaml` (Swagger — источник истины).

```
backend/
├── main.py            # WSGI-точка входа: gunicorn main:app (в __main__ — локальный запуск)
├── worker.py          # отдельный процесс: периодические уведомления о просроченных продуктах
├── app/
│   ├── __init__.py    # фабрика приложения create_app()
│   ├── config.py      # настройки только из переменных окружения
│   ├── context.py     # доступ к БД/настройкам текущего приложения
│   ├── db.py          # пул соединений psycopg2, транзакции, rollback, health-check
│   ├── errors.py      # ApiError и единый обработчик ошибок {"error": "..."}
│   ├── security.py    # JWT, @token_required, простой rate limit для /login и /register
│   ├── validation.py  # валидация входных данных (лимиты совпадают с типами колонок)
│   ├── serializers.py # date/datetime/строки -> JSON (имена колонок -> имена полей API)
│   ├── embeddings.py  # эмбеддинги (ленивая загрузка, включаются EMBEDDINGS_ENABLED)
│   ├── schema.sql     # DDL: 8 таблиц, индексы, 2 триггера истории (идемпотентный)
│   ├── migrate.py     # миграции: python -m app.migrate + журнал schema_migrations
│   ├── models/        # SQL-слой: по модулю на таблицу, только параметризованные запросы
│   ├── services/      # бизнес-логика
│   └── api/           # HTTP-слой (blueprint'ы по областям)
├── migrations/        # версионные SQL-миграции для существующих баз (0001_...sql, ...)
└── tests/             # pytest: контрактные тесты + тесты с реальной БД
```

### Запуск

```bash
cp .env.example .env            # в корне репозитория
docker compose up --build       # db + backend + frontend + swagger
```

Локально без Docker (нужен доступный PostgreSQL):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # укажите DATABASE_URL и JWT_SECRET
python main.py                  # http://localhost:8000
```

Проверки: `GET /health` (живость процесса), `GET /ready` (готовность БД),
Swagger UI — `http://localhost:${SWAGGER_PORT}/`.

### Схема БД

Структура соответствует `docs/db_scheme.png` (8 таблиц):

| Таблица | Назначение |
|---|---|
| `users` | пользователи: `username`, `password` (scrypt-хэш), `email`, `allergies`/`preferences` (термины через запятую) |
| `recipes` | рецепты: `recipe_name`, `ingredients`, `instruction`, `difficulty_level` |
| `fridge_items` | продукты: `item_id` (ключ), `user_id`, `product_name`, `expiration_date`, `quantity`, `last_added` |
| `favorite_recipes` | избранные рецепты пользователя |
| `generated_recipes` | что именно выдавали пользователю (`/suggest_recipes`, `/recommend_recipes`) |
| `user_allergy_preferences` | аллергии пользователя, по строке на термин |
| `fridge_item_versions` | история версий продукта (наполняется триггером) |
| `fridge_item_audit` | аудит действий с продуктами: `old_values`/`new_value` в JSONB |

Осознанные отклонения от диаграммы (они же — комментарии в `app/schema.sql`):

- `users.password varchar(200)` вместо `varchar(120)`: scrypt-хэш werkzeug занимает 162 символа;
- `fridge_item_versions.fridge_items_id ... ON DELETE SET NULL` (в диаграмме правило не указано):
  с `NO ACTION` падал бы `DELETE /delete_expired_products`, а история продукта терялась бы;
- `fridge_items.quantity integer NOT NULL DEFAULT 1 CHECK (quantity > 0)`: количество не может
  быть нулевым или дробным (в API это же ограничение описано как `integer`/`minimum: 1`);
- уникальный индекс `users_email_lower_key` по `lower(email)`: контракт считает email
  регистронезависимым;
- `NOT NULL DEFAULT current_timestamp` у timestamp-колонок (`last_added`, `action_time`,
  `updated_at`, `generated_on`) и `NOT NULL` у `fridge_item_versions.version`;
- `recipes.instruction` объявлена nullable, чтобы рецепт без инструкции не ломал API;
- `recipes.ingredients` названа правильно: в текстовом описании схемы (`docs/db_plan`) слово
  написано с опечаткой («igredients»), а `openapi.yaml` и SQL-запросы используют `ingredients`.

Изменения структуры БД оформляются миграциями (`backend/migrations`). `app/schema.sql` — это
целевое состояние для новой базы, миграции переведут в него уже существующую:

```bash
cd backend
python -m app.migrate    # применить неприменённые миграции, затем app/schema.sql
```

Воркер уведомлений (запускается отдельно от web-процесса):

```bash
python worker.py --once                 # один проход
python worker.py --interval-minutes 60  # цикл по расписанию
```

### Тесты и линтеры

Набор — 36 кейсов в 7 файлах: по 1–2 кейса на каждый из 19 адресов (успех + отказ) и отдельный
файл `tests/test_database.py` про саму схему БД. 11 кейсов идут без базы, 25 — против PostgreSQL.

```bash
cd backend
python -m pytest                # без БД: 11 passed, 25 skipped (DB-кейсы пропускаются)
TEST_DATABASE_URL=postgresql://postgres:changeme@localhost:5432/mydatabase python -m pytest
                                # с БД: 36 passed
ruff check app main.py worker.py tests
black --check app main.py worker.py tests
```

Полный прогон против реальной базы (`36 passed, 0 skipped`) проверен на этом коде: локально на
PostgreSQL 16.2 и в CI на PostgreSQL 15.

Полный перечень кейсов (чек-лист для отчётности): [TEST-CHECKLIST.md](TEST-CHECKLIST.md).

### CI (GitHub Actions)

- **Backend CI** (`.github/workflows/backend-tests.yml`) — на push в `main` и на каждый PR:
  Python 3.11, сервисный контейнер PostgreSQL 15, затем `ruff check .`, `black --check .`
  и `python -m pytest` (36 кейсов, DB-часть идёт против сервисной базы `recipes_test`;
  файл `tests/test_database.py` проверяет саму схему БД `docs/db_scheme.png` и триггеры истории).
  Отдельный шаг проверяет доступность БД, чтобы набор не «позеленел» на одних скипах
  (`tests/conftest.py` пропускает DB-тесты, когда `TEST_DATABASE_URL` недоступен).
- **Docker-пайплайн** (`.github/workflows/docker-image.yml`) — на push в `main`: сборка образов,
  `docker compose up -d` и smoke-проверка `/ready` + `/health`.

### Отличия от CONTRIBUTION.md, зафиксированные в коде

Контракт `openapi.yaml` приоритетнее внутренних правил, поэтому осознанно сохранены:

- `POST /user_preferences` — без JWT, `user_id` берётся из тела запроса;
- `POST /recipes` — без JWT;
- `GET /fridge_items` и `DELETE /delete_expired_products` — работают со всеми пользователями;
- формат ошибок — `{"error": "<строка>"}`; JWT живёт 12 часов; пагинации нет.
