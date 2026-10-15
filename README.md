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
│   ├── validation.py  # валидация входных данных
│   ├── serializers.py # date/datetime/Decimal -> JSON
│   ├── embeddings.py  # эмбеддинги (ленивая загрузка, включаются EMBEDDINGS_ENABLED)
│   ├── schema.sql     # DDL (идемпотентный, применяется при AUTO_INIT_SCHEMA=true)
│   ├── models/        # SQL-слой (только параметризованные запросы)
│   ├── services/      # бизнес-логика
│   └── api/           # HTTP-слой (blueprint'ы по областям)
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

Воркер уведомлений (запускается отдельно от web-процесса):

```bash
python worker.py --once                 # один проход
python worker.py --interval-minutes 60  # цикл по расписанию
```

### Тесты и линтеры

```bash
cd backend
python -m pytest                # DB-тесты пропускаются, если TEST_DATABASE_URL недоступен
TEST_DATABASE_URL=postgresql://postgres:changeme@localhost:5432/mydatabase python -m pytest
ruff check app main.py worker.py tests
black --check app main.py worker.py tests
```

Полный перечень кейсов (чек-лист для отчётности): [TEST-CHECKLIST.md](TEST-CHECKLIST.md).

### CI (GitHub Actions)

- **Backend CI** (`.github/workflows/backend-tests.yml`) — на push в `main` и на каждый PR:
  Python 3.11, сервисный контейнер PostgreSQL 15, затем `ruff check .`, `black --check .`
  и `python -m pytest` (76 тестов, DB-часть идёт против сервисной базы `recipes_test`).
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
