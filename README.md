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
│   ├── ml/            # ML-модуль: предобработка, векторизация, TF-IDF модель v1, KNN, аллергены, метрики
│   ├── importer/      # импорт датасета povarenok: чтение, нормализация, CLI, скачивание
│   ├── schema.sql     # DDL: 9 таблиц, индексы, 3 триггера (идемпотентный)
│   ├── migrate.py     # миграции: python -m app.migrate + журнал schema_migrations
│   ├── models/        # SQL-слой: по модулю на таблицу, только параметризованные запросы
│   ├── services/      # бизнес-логика
│   └── api/           # HTTP-слой (blueprint'ы по областям)
├── migrations/        # версионные SQL-миграции для существующих баз (0001_...sql, ...)
├── requirements-ml.txt# необязательные зависимости импорта (pyarrow для parquet)
└── tests/             # pytest: контрактные тесты + тесты с реальной БД
    └── data/          # сэмпл датасета, размеченная выборка аллергенов, корпус для метрик
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

### Поля карточки рецепта

Ответ любого адреса, который возвращает рецепт (`GET /recipes`, `GET /recipes/{id}`,
`GET /favorite_recipes`, `GET /suggest_recipes`, оба режима `GET /recommend_recipes`), — один
и тот же объект `Recipe` из `openapi.yaml`:

| Поле | Что это | Бывает `null` |
|---|---|---|
| `id`, `name` | идентификатор и название (`recipes.recipe_name`) | – |
| `ingredients` | тот же состав текстом, «продукт — количество» через запятую (`recipes.ingredients`) | – |
| `ingredient_list` | `[{"name", "quantity"}]` из `recipe_ingredients`, в порядке `sort_order` — ровно то, по чему работает фильтр аллергенов | `[]` у рецептов, созданных через `POST /recipes` (структурные строки пишет только импортёр) |
| `instructions` | инструкция (`recipes.instruction`, `text`) | да, у импортированных рецептов |
| `difficulty_level` | сложность (`varchar(50)`) | да, у импортированных рецептов |
| `source_url` | ссылка на источник и естественный ключ импорта (`varchar(255)`) | да, у рецептов, созданных через API |

Почему так: в датасете povarenok нет ни инструкций, ни сложности, поэтому `POST /recipes`
требует эти поля (ручной рецепт полный), а импортированный отдаёт `null` — иначе пришлось бы
выдумывать данные. Импортировать и создавать вручную можно в одной базе, поэтому клиент должен
быть готов к обоим вариантам; схема это разрешает явно (`nullable: true`).

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
| векторизация | `app/ml/vectorizer.py`, `app/ml/model.py` | TF-IDF v1 из артефакта (`SMART_RECOMMENDATIONS_ARTIFACT`), иначе bag-of-lemmas; SBERT — только при `EMBEDDINGS_ENABLED` |
| обучающая выборка | `app/ml/engine.py`, `app/ml/corpus.py` | каталог рецептов из БД (`recipe_ingredients`, текст — запасной вариант) либо файл датасета |
| избранное и «холодный старт» | `app/ml/engine.py` | профиль — центроид избранного; без него — продукты холодильника |
| KNN | `app/ml/knn.py` | чистый Python вместо `sklearn.neighbors` (данных на один запрос мало) |
| фильтрация | `app/ml/allergens.py`, `app/services/allergen_service.py` | словарь групп с синонимами и словоформами, фильтр по строкам `recipe_ingredients`; ложные срабатывания (кокос, гречка) исключены правилами |
| контекстная адаптация | `app/ml/engine.py` | бонус за продукты из холодильника (`FRIDGE_BONUS = 0.2`) к косинусной близости |
| оценка качества | `app/ml/allergen_eval.py`, `app/ml/evaluate.py` | precision/recall/F1 аллергенов и метрики ранжирования рекомендаций |

Модуль включается флагом, адрес при этом не меняется: `GET /recommend_recipes` отвечает в том
же формате `message` + `recipes`, что и раньше, — переключается только внутренняя логика
(`app/services/smart_recommendation_service.py`).

```bash
SMART_RECOMMENDATIONS_ENABLED=false  # базовая логика (как до модуля) — значение по умолчанию
SMART_RECOMMENDATIONS_ENABLED=true   # ML-модуль
SMART_RECOMMENDATIONS_LIMIT=5        # размер ответа (top-5 на диаграмме ml_plan)
SMART_RECOMMENDATIONS_NEIGHBOURS=10  # сколько соседей рассматривает KNN
SMART_RECOMMENDATIONS_ARTIFACT=      # путь к обученной модели (по умолчанию app/ml/artifacts/v1.json)
```

Переключатель проверяется тестами: `tests/test_smart_recommendations.py` прогоняет один и тот же
набор данных дважды — с флагом и без него. Чего в заглушке ещё нет: действительное обучение SBERT
на истории выдач и полноценная морфология.

### Модель рекомендаций v1 (TF-IDF)

Задача 6.0/6.2 научила модуль взвешивать ингредиенты: вместо bag-of-lemmas (каждое слово весит
1.0, поэтому `соль` и `масло` тянут ответ так же сильно, как `шафран`) используется TF-IDF с
IDF, обученными на каталоге рецептов. Модель — один JSON-артефакт; нет файла — работает прежняя
заглушка, сервис не падает.

```bash
cd backend
python -m app.ml.model                 # обучить на корпусе репозитория (120 рецептов)
python -m app.ml.model --from-db       # обучить на импортированном каталоге (DATABASE_URL)
python -m app.ml.evaluate              # метрики v1 против baseline, код возврата 1 при регрессе
```

Замер на корпусе `backend/tests/data/recommendation_sample.json` (120 рецептов, 813 запросов,
leave-one-ingredient-out, `k = 5`):

| Стратегия | P@1 | P@5 | R@5 | Hit@5 | MRR@5 |
|---|---|---|---|---|---|
| baseline (bag-of-lemmas) | 0.385 | 0.326 | 0.344 | 0.672 | 0.493 |
| v1 (TF-IDF) | 0.395 | **0.360** | **0.380** | **0.711** | **0.513** |

`P@5` выросла на 3,3 п.п. (+10 % относительно), `MRR@5` — на 0.020: критерий задачи (v1 выше
baseline по `P@5` и `MRR`) выполнен. Протокол измерения, разбивка по частоте продуктов,
ограничения и команды воспроизведения — в [docs/recommendation-model.md](docs/recommendation-model.md).

### Аллергии и непереносимости

Фильтрация по аллергенам вынесена в `app/ml/allergens.py`: 13 групп (`milk`, `gluten`, `eggs`,
`soy`, `peanut`, `nuts`, `fish`, `seafood`, `sesame`, `mustard`, `celery`, `sulphites`, `lupin`)
с русскими и английскими синонимами и словоформами. Термин пользователя из
`user_allergy_preferences` («молочные продукты», «глютен») раскрывается в группу, поэтому
«сливки» и «творог» тоже отбрасываются. Сравнение идёт по леммам и по строкам
`recipe_ingredients` (их заполняет импортёр); текст `recipes.ingredients` используется только как
запасной вариант для рецептов, созданных через `POST /recipes`.

Ложные срабатывания исключены правилами, а не списком исключений «на глаз»:

- `blockers` — фраза, которая превращает продукт в безопасный заменитель: «кокосовое молоко» это
  не молоко, «гречневая мука» и «соевая мука» — не глютен, «томатная паста» — не макароны;
- `exceptions` — слова-двойники: «картофель сырой» — не «сыр», «печень» — не «печенье»,
  `eggplant` — не яйцо;
- аллергия, которой нет в словаре («киви»), остаётся обычным термином и всё равно фильтрует.

Качество измеряется на вручную размеченной выборке (`backend/tests/data/allergen_labeled_sample.json`,
211 рецептов, 259 меток) скриптом:

```bash
cd backend
python -m app.ml.allergen_eval          # precision / recall / F1 / violation_rate + таблица по группам
python -m app.ml.allergen_eval --json   # то же машинно-читаемо
```

Последний прогон: precision = 1.000, recall = 1.000, F1 = 1.000, `violation_rate = 0.000`
(пропущенных аллергенов нет — это обязательный критерий задачи). Подробности, ограничения и
команды воспроизведения — в [docs/allergen-filter.md](docs/allergen-filter.md).


Набор — 93 кейса в 13 файлах: по 1–3 кейса на каждый из 22 адресов (успех + отказ), отдельный
файл `tests/test_database.py` про саму схему БД, `tests/test_favorites.py` про избранное, четыре
файла про ML-модуль (`test_ml_engine.py`, `test_smart_recommendations.py`, `test_allergens.py`,
`test_recommendation_model.py`) и `tests/test_importer_povarenok.py` про импорт датасета.
43 кейса идут без базы, 50 — против PostgreSQL.

```bash
cd backend
python -m pytest                # без БД: 43 passed, 50 skipped (DB-кейсы пропускаются)
TEST_DATABASE_URL=postgresql://postgres:changeme@localhost:5432/mydatabase python -m pytest
                                # с БД: 93 passed
ruff check app main.py worker.py tests
black --check app main.py worker.py tests

# покрытие и порог 80 % (docs/test-coverage.md)
TEST_DATABASE_URL=postgresql://postgres:changeme@localhost:5432/mydatabase \
  coverage run -m pytest && coverage report
```

Полный прогон против реальной базы (`93 passed, 0 skipped`) проверен на этом коде локально
(PostgreSQL 15 в контейнере) и в CI на PostgreSQL 15.

### Покрытие тестами

Измерено `coverage.py` на полном наборе с PostgreSQL: **87,7 % строк** (2055 из 2342) и
**81,1 % ветвей** (684 из 843), комбинированное покрытие — 86,0 %. Порог 80 % записан в
`backend/pyproject.toml` (`[tool.coverage.report] fail_under`) и проверяется в CI, поэтому
просадка покрытия ломает сборку.

Фильтр аллергенов (`app/ml/allergens.py` и `app/services/allergen_service.py`) покрыт на 100 %
и по строкам, и по ветвям — это осознанное требование: цена ошибки здесь не сломанная страница,
а аллерген в рекомендации. Модули задачи 5 (`recipe_presenter`, `serializers`) — тоже 100 %.

Что не покрыто и почему (эмбеддинги требуют `requirements-ml.txt`, `migrate.py` — отдельной
пустой базы, `fridge_history.py` — мёртвый код) — в [docs/test-coverage.md](docs/test-coverage.md),
там же соответствие ГОСТ Р 56920/56921/56922-2016, ГОСТ 34.603-92, ГОСТ 19.301-79 и
ГОСТ Р ИСО/МЭК 25010-2015.

Полный перечень кейсов (чек-лист для отчётности): [TEST-CHECKLIST.md](TEST-CHECKLIST.md).

### CI (GitHub Actions)

- **Backend CI** (`.github/workflows/backend-tests.yml`) — на push в `main` и на каждый PR:
  Python 3.11, сервисный контейнер PostgreSQL 15, затем `ruff check .`, `black --check .`,
  обучение модели с проверкой метрик и весь набор под `coverage` (93 кейса, DB-часть идёт против
  сервисной базы `recipes_test`; файл `tests/test_database.py` проверяет саму схему БД
  `docs/db_scheme.png` и триггеры истории).
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
