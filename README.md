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
│   ├── ml/            # заглушка ML-модуля: предобработка, векторизация, KNN, фильтрация
│   ├── importer/      # импорт датасета povarenok: чтение, нормализация, CLI, скачивание
│   ├── schema.sql     # DDL: 9 таблиц, индексы, 3 триггера (идемпотентный)
│   ├── migrate.py     # миграции: python -m app.migrate + журнал schema_migrations
│   ├── models/        # SQL-слой: по модулю на таблицу, только параметризованные запросы
│   ├── services/      # бизнес-логика
│   └── api/           # HTTP-слой (blueprint'ы по областям)
├── migrations/        # версионные SQL-миграции для существующих баз (0001_...sql, ...)
├── requirements-ml.txt# необязательные зависимости импорта (pyarrow для parquet)
└── tests/             # pytest: контрактные тесты + тесты с реальной БД
    └── data/          # синтетический сэмпл датасета вместо сырых данных
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

Структура соответствует `docs/db_scheme.png` (9 таблиц; подробное описание каждой колонки,
индекса и триггера — [docs/db_schema.md](docs/db_schema.md)):

| Таблица | Назначение |
|---|---|
| `users` | пользователи: `username`, `password` (scrypt-хэш), `email`, `allergies`/`preferences` (термины через запятую) |
| `recipes` | рецепты: `recipe_name`, `ingredients`, `instruction`, `difficulty_level`, `source_url` (ключ импорта), `created_at`/`updated_at` |
| `recipe_ingredients` | ингредиенты рецепта по строкам: `ingredient_name`, `quantity_text`, `sort_order` |
| `fridge_items` | продукты: `item_id` (ключ), `user_id`, `product_name`, `expiration_date`, `quantity`, `last_added` |
| `favorite_recipes` | избранные рецепты пользователя (`created_at` — порядок выдачи) |
| `generated_recipes` | что именно выдавали пользователю (`/suggest_recipes`, `/recommend_recipes`) |
| `user_allergy_preferences` | аллергии пользователя, по строке на термин |
| `fridge_item_versions` | история версий продукта (наполняется триггером) |
| `fridge_item_audit` | аудит действий с продуктами: `old_values`/`new_value` в JSONB |

Расширения под импорт датасета povarenok (подробно — [docs/db_schema.md](docs/db_schema.md)):

- `recipes.source_url` — естественный ключ импортированного рецепта (`UNIQUE`; у ручных рецептов
  `NULL`, поэтому повторный импорт идемпотентен: `ON CONFLICT (source_url) DO NOTHING`);
- `recipe_ingredients` — ингредиенты рецепта по строкам (`ingredient_name`, `quantity_text`,
  `sort_order`): словарь `{ингредиент: количество}` из датасета, разложенный по таблице;
- `recipes.created_at`/`updated_at` и `favorite_recipes.created_at` — метки времени;
  `updated_at` обновляет триггер `recipes_updated_at_trigger`, а не код приложения.

Осознанные отклонения от диаграммы (они же — комментарии в `app/schema.sql`):

- `users.password varchar(200)` вместо `varchar(120)`: scrypt-хэш werkzeug занимает 162 символа;
- `fridge_item_versions.fridge_items_id ... ON DELETE SET NULL` (в диаграмме правило не указано):
  с `NO ACTION` падал бы `DELETE /delete_expired_products`, а история продукта терялась бы;
- `fridge_items.quantity integer NOT NULL DEFAULT 1 CHECK (quantity > 0)`: количество не может
  быть нулевым или дробным (в API это же ограничение описано как `integer`/`minimum: 1`);
- уникальный индекс `users_email_lower_key` по `lower(email)`: контракт считает email
  регистронезависимым;
- `NOT NULL DEFAULT current_timestamp` у timestamp-колонок (`last_added`, `action_time`,
  `updated_at`, `generated_on`, `created_at`) и `NOT NULL` у `fridge_item_versions.version`;
- `recipes.instruction` объявлена `text` и nullable: инструкция не помещается в 100 символов, а у
  импортированных рецептов её нет вовсе; API принимает до 10 000 символов
  (`MAX_INSTRUCTION_LENGTH`), как и объявлено в `openapi.yaml`;
- `recipes.ingredients` названа правильно: в текстовом описании схемы (`docs/db_plan`) слово
  написано с опечаткой («igredients»), а `openapi.yaml` и SQL-запросы используют `ingredients`.

Изменения структуры БД оформляются миграциями (`backend/migrations`, последняя —
`0002_recipe_ingredients.sql`). `app/schema.sql` — это целевое состояние для новой базы, миграции
переведут в него уже существующую:

```bash
cd backend
python -m app.migrate    # применить неприменённые миграции, затем app/schema.sql
```

Воркер уведомлений (запускается отдельно от web-процесса):

```bash
python worker.py --once                 # один проход
python worker.py --interval-minutes 60  # цикл по расписанию
```

### Просроченные продукты

«Просрочен» — значит срок истёк до сегодняшнего дня: продукт со сроком «сегодня» ещё
годен. Правило задано один раз (`EXPIRED_CONDITION` в `app/models/fridge.py`) и считается
по дате базы данных (`CURRENT_DATE`), а не по часам web-процесса: сервис и база могут жить
в разных часовых поясах, иначе `GET /notify_expired` и `DELETE /delete_expired_products`
расходились бы около полуночи. Тем же правилом пользуются `DELETE /delete_expired`,
`GET /suggest_recipes` и воркер уведомлений.

Проверяется кейсами `test_delete_expired_products_uses_the_database_date_as_the_boundary`
(граница «вчера / сегодня / завтра» и повторное удаление) и
`test_notify_expired_and_delete_expired_products_use_one_rule` (отчёт и удаление совпадают).

### Импорт датасета povarenok

Реальные рецепты приходят из открытого датасета Kaggle
[`rogozinushka/povarenok-recipes`](https://www.kaggle.com/datasets/rogozinushka/povarenok-recipes):
~147 тыс. строк, поля `url`, `name`, `ingredients`. Лицензия не указана, поэтому **сырые данные не
коммитятся и не попадают в образ**: `.gitignore` и `backend/.dockerignore` исключают
`backend/data/`, а в репозитории лежит только синтетический сэмпл
`backend/tests/data/povarenok_sample.json` (12 рецептов, 60 строк ингредиентов).

```bash
cd backend
pip install -r requirements-ml.txt        # pyarrow — только для чтения parquet
export KAGGLE_USERNAME=... KAGGLE_KEY=... # доступ к Kaggle только через переменные окружения

python -m app.importer --download --destination data/povarenok   # скачать и распаковать архив
python -m app.importer --dataset tests/data/povarenok_sample.json --dry-run
python -m app.importer --dataset data/povarenok --limit 1000 --batch-size 1000
```

| Что | Как устроено |
|---|---|
| форматы | CSV (родной формат датасета), JSON/JSONL и parquet; формат определяется по расширению |
| `ingredients` | словарь в трёх видах: Python-литерал из CSV (`{'Соль': None}`), JSON-строка, список строк `"name: amount"`; `ast.literal_eval` не исполняет код из файла |
| запись | `recipes` (`source_url`, `recipe_name`, `ingredients`, `instruction = NULL`, `difficulty_level = NULL`) + `recipe_ingredients` (`ingredient_name`, `quantity_text`, `sort_order`) |
| идемпотентность | `source_url` — естественный ключ, `ON CONFLICT (source_url) DO NOTHING`: повторный импорт не создаёт дублей, а `--limit` позволяет продолжить с места остановки |
| память | потоковое чтение и пачки по `--batch-size` (по умолчанию 1000), каждая пачка — одна транзакция |
| прогресс | `logging` по каждой пачке и итоговые счётчики (`recipes_inserted`, `recipes_duplicated`, `ingredients_inserted`), без персональных данных |
| сеть | скачивание — стандартный `urllib` с таймаутом (`--timeout`, по умолчанию 120 с) и Basic-авторизацией Kaggle; архив распаковывается с защитой от `../`-путей |

Замеры на синтетическом CSV в формате датасета (50 тыс. строк, 12,5 МБ): `--dry-run` — 3,0 с и
72 МиБ пиковой памяти; импорт 20 тыс. рецептов (100 тыс. строк ингредиентов) — 6,8 с и те же
72 МиБ; повторный запуск — 2,0 с, вставлено 0 записей (20 тыс. дублей). Память не растёт вместе
с файлом. `kagglehub` и `pandas` не понадобились: скачивание — стандартный `urllib`, CSV читает
`csv` из стандартной библиотеки, parquet — `pyarrow` из `requirements-ml.txt`.

`GET /recipes` отдаёт страницы (`?limit=&offset=`; по умолчанию 50, максимум 200) — без этого
147 тыс. рецептов в одном ответе были бы неприемлемы.

### Модуль рекомендаций (заглушка ML)

`app/ml` — минимальная рабочая версия рекомендательного модуля из `ml_planning/ml_plan`
(«меньше, чем MVP»): конвейер проходит целиком и отвечает на реальные запросы, но внутри
стоят намеренно простые решения — новых зависимостей и таблиц модуль не требует.

| Компонент (`ml_plan`) | Где реализован | Чем заглушка отличается от целевого решения |
|---|---|---|
| предобработка данных | `app/ml/preprocessing.py` | нормализация и стоп-слова точные, лемматизация — таблица окончаний вместо `pymorphy2` |
| векторизация | `app/ml/vectorizer.py` | SBERT при `EMBEDDINGS_ENABLED`, иначе разреженный bag-of-lemmas (без `torch` в старте) |
| обучающая выборка | `app/ml/engine.py` | избранное пользователя (`favorite_recipes`); без него — «холодный старт» по холодильнику |
| KNN | `app/ml/knn.py` | чистый Python вместо `sklearn.neighbors` (данных на один запрос мало) |
| фильтрация | `app/ml/engine.py` | аллергены из `user_allergy_preferences` сравниваются по леммам |
| контекстная адаптация | `app/ml/engine.py` | бонус за продукты из холодильника (`FRIDGE_BONUS = 0.2`) к косинусной близости |

Модуль включается флагом, адрес при этом не меняется: `GET /recommend_recipes` отвечает в том
же формате `message` + `recipes`, что и раньше, — переключается только внутренняя логика
(`app/services/smart_recommendation_service.py`).

```bash
SMART_RECOMMENDATIONS_ENABLED=false  # базовая логика (как до модуля) — значение по умолчанию
SMART_RECOMMENDATIONS_ENABLED=true   # заглушка ML-модуля
SMART_RECOMMENDATIONS_LIMIT=5        # размер ответа (top-5 на диаграмме ml_plan)
SMART_RECOMMENDATIONS_NEIGHBOURS=10  # сколько соседей рассматривает KNN
```

Переключатель проверяется тестами: `tests/test_smart_recommendations.py` прогоняет один и тот же
набор данных дважды — с флагом и без него. Чего в заглушке ещё нет (следующий шаг работы):
действительное обучение SBERT на истории выдач, полноценная морфология, метрики качества.


Набор — 65 кейсов в 11 файлах: по 1–3 кейса на каждый из 22 адресов (успех + отказ), отдельный
файл `tests/test_database.py` про саму схему БД, `tests/test_favorites.py` про избранное, два
файла про заглушку ML-модуля и `tests/test_importer_povarenok.py` про импорт датасета.
21 кейс идёт без базы, 44 — против PostgreSQL.

```bash
cd backend
python -m pytest                # без БД: 21 passed, 44 skipped (DB-кейсы пропускаются)
TEST_DATABASE_URL=postgresql://postgres:changeme@localhost:5432/mydatabase python -m pytest
                                # с БД: 65 passed
ruff check app main.py worker.py tests
black --check app main.py worker.py tests
```

Полный прогон против реальной базы (`65 passed, 0 skipped`) проверен на этом коде локально
(PostgreSQL 15 в контейнере) и в CI на PostgreSQL 15.

Полный перечень кейсов (чек-лист для отчётности): [TEST-CHECKLIST.md](TEST-CHECKLIST.md).

### CI (GitHub Actions)

- **Backend CI** (`.github/workflows/backend-tests.yml`) — на push в `main` и на каждый PR:
  Python 3.11, сервисный контейнер PostgreSQL 15, затем `ruff check .`, `black --check .`
  и `python -m pytest` (65 кейсов, DB-часть идёт против сервисной базы `recipes_test`;
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
- формат ошибок — `{"error": "<строка>"}`; JWT живёт 12 часов; пагинация есть у `GET /recipes`,
  `GET /fridge_items` и `GET /favorite_recipes` (`limit`/`offset`), остальные списки отдаются целиком.
