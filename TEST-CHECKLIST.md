# Чек-лист тестов API

Файл для отчётности по спринту: полный перечень автоматических тестов backend
(`backend/tests/`, `pytest`) и ожидаемое поведение каждого кейса.

**Состав набора:** 53 тестовые функции, **76 кейсов** (28 кейсов получены параметризацией),
46 кейсов работают с реальной PostgreSQL, 30 — контрактные (без БД).

## Как запускать

```bash
cd backend
python -m pytest                 # без БД: 30 passed, 46 skipped (DB-тесты скипаются)
TEST_DATABASE_URL=postgresql://postgres:changeme@localhost:5432/mydatabase python -m pytest
                                 # с БД: 76 passed
```

То же самое автоматически выполняется в CI: workflow `Backend CI`
(`.github/workflows/backend-tests.yml`) поднимает PostgreSQL 15 и запускает
`python -m pytest` на каждый push в `main` и на каждый pull request.

## Итог прогона (последняя проверка)

| Файл | Кейсов | Функций | С БД | Статус |
|---|---|---|---|---|
| `tests/test_auth.py` | 20 | 15 | 7 | ✅ passed |
| `tests/test_recipes.py` | 14 | 10 | 14 | ✅ passed |
| `tests/test_fridge.py` | 14 | 7 | 14 | ✅ passed |
| `tests/test_notifications_recommendations.py` | 12 | 10 | 8 | ✅ passed |
| `tests/test_user_preferences.py` | 9 | 4 | 2 | ✅ passed |
| `tests/test_system.py` | 7 | 7 | 1 | ✅ passed |
| **Всего** | **76** | **53** | **46** | ✅ **76 passed, 0 failed, 0 skipped** |

Проверено 15.10.2026 на этом же коде: с живым PostgreSQL — `76 passed, 0 skipped` (exit 0, ~5 с);
без БД — `30 passed, 46 skipped` (exit 0); `ruff check .` и `black --check .` — без замечаний.

## Покрытие эндпоинтов (CONTRIBUTION.md §10)

| Эндпоинт | Успешный сценарий | Негативные сценарии |
|---|---|---|
| `GET /` | ✅ 200, текстовое приветствие | — (общий обработчик 404/405 проверен на других маршрутах) |
| `GET /health` | ✅ 200 `{"status":"ok"}` без БД | — (liveness не зависит от БД) |
| `GET /ready` | ✅ 200 `{"database":"ok"}` | ✅ 503 `{"database":"unavailable"}` |
| `POST /register` | ✅ 201, строки и списки в `allergies`/`preferences` | ✅ 400 ×7 (тело и валидация полей), 400 дубликат email, 400 дубликат username |
| `POST /login` | ✅ 200 + `token` | ✅ 400 нет email/password, 401 неизвестный пользователь, 401 неверный пароль |
| `GET /protected` | ✅ 200 `{"message","user_id"}` | ✅ 401 в 4 тестах (6 проверок): нет заголовка, схема не Bearer, пустой токен, битый токен, просроченный, без `sub` |
| `POST /user_preferences` | ✅ 200 + запись проверена SQL-запросом | ✅ 400 ×7 (валидация тела), 400 неизвестный `user_id` |
| `POST /recipes` | ✅ 201 | ✅ 400 ×6 (нет обязательного поля ×5, неверный тип) |
| `GET /recipes` | ✅ 200 список, состав полей | ✅ 404 для несуществующего id |
| `GET /recipes/{id}` | ✅ 200 одиночный рецепт | ✅ 404 |
| `PUT /recipes/{id}` | ✅ 200 + изменение сохранено | ✅ 400 неполное тело, 404 |
| `DELETE /recipes/{id}` | ✅ 200 + рецепт исчез, список пуст | ✅ 404 |
| `POST /fridge_items` | ✅ 201 | ✅ 400 ×10 (8 некорректных тел, пустой список, неизвестный пользователь) |
| `GET /fridge_items` | ✅ 200, поля item | — (по `openapi.yaml` маршрут без токена, негативных кейсов нет) |
| `DELETE /delete_expired_products` | ✅ 200, только просроченные, повторный вызов идемпотентен | — |
| `GET /notify_expired` | ✅ 200 со списком просроченного, 200 при пустом холодильнике | ✅ 401 ×2 (нет токена, битый токен) |
| `DELETE /delete_expired` | ✅ 200, удаляет только продукты текущего пользователя | ✅ 401 |
| `GET /suggest_recipes` | ✅ 200 рецепт из просроченных продуктов, 200 без просроченных | ✅ 401 ×2 |
| `GET /recommend_recipes` | ✅ 200, аллергены исключены, 200 при пустом холодильнике | ✅ 401 ×2, 401 токен неизвестного пользователя |
| Неизвестный путь | — | ✅ 404 в формате `{"error": ...}` |
| Недопустимый метод (`DELETE /login`) | — | ✅ 405 в формате `{"error": ...}` |

## Чек-лист по файлам

Обозначения: `[x]` — кейс есть в наборе и проходит; **(БД)** — выполняется против реальной
PostgreSQL; **(контракт)** — выполняется на приложении без БД (валидация, авторизация, пробы).
Идентификаторы совпадают с выводом `pytest -v`. Параметризованные функции оформлены строкой-группой
без чекбокса, а каждый параметризованный кейс — отдельным чекбоксом, поэтому **число `[x]` в файле
равно числу тестов (76)**.

### `tests/test_auth.py` — авторизация (20 кейсов)

**`POST /register`**

- [x] `test_register_requires_a_json_object` (контракт) — тело не является JSON → `400` + ключ `error`.
- `test_register_rejects_invalid_payloads` (контракт) — группа из 6 кейсов, все ✅: некорректное тело → `400` + ключ `error`:
  - [x] `[payload0]` пустое тело `{}`;
  - [x] `[payload1]` нет `password`;
  - [x] `[payload2]` email не по формату (`not-an-email`);
  - [x] `[payload3]` слишком короткий пароль (`short`);
  - [x] `[payload4]` `username` из одних пробелов;
  - [x] `[payload5]` `allergies = 42` (не строка и не список).
- [x] `test_register_creates_a_user` (БД) — корректная регистрация → `201`, `user_id` — целое, есть `message`.
- [x] `test_register_accepts_string_and_list_terms` (БД) — `allergies` строкой и `preferences` списком сохраняются без изменений → `201`.
- [x] `test_register_rejects_duplicate_email` (БД) — повторный email при другом username → `400`, в тексте ошибки есть `email`.
- [x] `test_register_rejects_duplicate_username` (БД) — повторный username при другом email → `400`, в тексте ошибки есть `username`.

**`POST /login`**

- [x] `test_login_requires_email_and_password` (контракт) — пустое тело и тело без `password` → `400`.
- [x] `test_login_returns_token` (БД) — верные email и пароль → `200` и непустой `token`.
- [x] `test_login_rejects_unknown_user` (БД) — незарегистрированный email → `401` + ключ `error`.
- [x] `test_login_rejects_wrong_password` (БД) — неверный пароль → `401`.

**`GET /protected`**

- [x] `test_protected_requires_a_bearer_token` (контракт) — нет заголовка, схема `Token abc`, пустой `Bearer ` → `401` (3 проверки).
- [x] `test_protected_rejects_a_malformed_token` (контракт) — `Bearer not-a-jwt` → `401`.
- [x] `test_protected_rejects_an_expired_token` (контракт) — токен с `exp` в прошлом → `401`.
- [x] `test_protected_rejects_a_token_without_subject` (контракт) — токен без `sub` → `401`.
- [x] `test_protected_accepts_a_valid_token` (контракт) — валидный токен → `200` и `{"message": "Access granted", "user_id": "5"}` (`user_id` строкой по `openapi.yaml`).

### `tests/test_recipes.py` — рецепты (14 кейсов, все с БД)

**`POST /recipes`**

- `test_create_recipe_requires_all_fields` (БД) — группа из 5 кейсов, все ✅: отсутствие обязательного поля → `400`, имя поля упомянуто в тексте ошибки:
  - [x] `[name]` — нет названия;
  - [x] `[ingredients]` — нет ингредиентов;
  - [x] `[instructions]` — нет инструкции;
  - [x] `[cuisine_type]` — нет типа кухни;
  - [x] `[difficulty_level]` — нет сложности.
- [x] `test_create_recipe_rejects_wrong_types` — `name` передан списком → `400`.
- [x] `test_create_recipe_does_not_require_a_token` — `POST /recipes` без JWT (по `openapi.yaml` защита отключена) → `201` + `message`.

**`GET /recipes`, `GET /recipes/{id}`**

- [x] `test_create_and_read_recipes` — создание → `201`; список → `200`, ровно один рецепт с целочисленным `id` и всеми переданными полями; запрос по id → `200` и тот же объект.
- [x] `test_get_unknown_recipe_returns_404` — `GET /recipes/424242` → `404`, id указан в тексте ошибки.

**`PUT /recipes/{id}`**

- [x] `test_update_recipe` — обновление имени и сложности → `200` + `message`, изменения видны в `GET /recipes/{id}`.
- [x] `test_update_recipe_validates_the_body` — тело только с `name` → `400`.
- [x] `test_update_unknown_recipe_returns_404` — `PUT /recipes/424242` → `404`.

**`DELETE /recipes/{id}`**

- [x] `test_delete_recipe` — удаление → `200` + `message`; повторный `GET /recipes/{id}` → `404`; список рецептов пуст.
- [x] `test_delete_unknown_recipe_returns_404` — `DELETE /recipes/424242` → `404`.

### `tests/test_fridge.py` — холодильник (14 кейсов, все с БД)

**`POST /fridge_items`**

- `test_add_items_rejects_invalid_payloads` (БД) — группа из 8 кейсов, все ✅: некорректное тело → `400` + ключ `error`:
  - [x] `[payload0]` объект вместо списка (`{"user_id": 1}`);
  - [x] `[payload1]` элемент списка — строка, а не объект;
  - [x] `[payload2]` пустой объект `{}` — нет обязательных полей;
  - [x] `[payload3]` нет `quantity`;
  - [x] `[payload4]` `quantity = 0` (нарушает `CHECK (quantity > 0)` в схеме БД);
  - [x] `[payload5]` `expiration_date = "01.01.2026"` — не ISO 8601;
  - [x] `[payload6]` `user_id = 0` — несуществующий пользователь;
  - [x] `[payload7]` `product_name` из одних пробелов.
- [x] `test_add_items_requires_at_least_one_item` — пустой список `[]` → `400`.
- [x] `test_add_items_rejects_unknown_user` — `user_id = 999999` → `400`, id указан в тексте ошибки.

**`GET /fridge_items`**

- [x] `test_add_and_list_items` — добавление позиции → `201`; список → `200`, один элемент с целочисленным `id`, верными `user_id`, `product_name`, `expiration_date` (ISO), `quantity` и заполненным `last_added`.
- [x] `test_list_items_returns_items_of_every_user` — позиции двух разных пользователей видны в общем списке (поведение зафиксировано по `openapi.yaml`).

**`DELETE /delete_expired_products`**

- [x] `test_delete_expired_products_removes_only_expired_items` — из трёх позиций (вчера, сегодня, завтра) удаляется только вчерашняя → `200` и `message = "Deleted 1 expired product(s)"`, остаются «fresh bread» и «expires today».
- [x] `test_delete_expired_products_is_idempotent` — повторный вызов → `200` и `message = "Deleted 0 expired product(s)"` (регрессия на «сломанную ссылку на дату» из `openapi.yaml`).

### `tests/test_notifications_recommendations.py` — уведомления и рекомендации (12 кейсов)

**Требования авторизации (контрактные)**

- `test_get_endpoints_require_a_token` (контракт) — группа из 3 кейсов, все ✅: без токена и с битым `Bearer invalid` → `401`:
  - [x] `[/notify_expired]`;
  - [x] `[/suggest_recipes]`;
  - [x] `[/recommend_recipes]`.
- [x] `test_delete_expired_requires_a_token` — `DELETE /delete_expired` без токена → `401`.

**`GET /notify_expired`**

- [x] `test_notify_expired_without_products` (БД) — пустой холодильник → `200` и `{"message": "No expired products found"}`.
- [x] `test_notify_expired_lists_the_products` (БД) — просроченный и свежий продукты → `200`, в `expired_products` только «sour milk» с ISO-датой и целочисленным `id`.

**`DELETE /delete_expired` (защищённый, работает только со своими данными)**

- [x] `test_delete_expired_touches_only_the_current_user` (БД) — у двух пользователей по просроченному продукту; вызов от первого → `200` и `Deleted 1 expired product(s)`, в БД остаётся продукт второго пользователя.

**`GET /suggest_recipes`**

- [x] `test_suggest_recipes_uses_expired_products` (БД) — в рецептах «Milk soup» и «Peanut cookies», просрочен только `milk` → `200` и в ответе ровно `["Milk soup"]`.
- [x] `test_suggest_recipes_without_expired_products` (БД) — просроченных продуктов нет → `200`, есть `message`, поля `recipes` в ответе нет.

**`GET /recommend_recipes`**

- [x] `test_recommend_recipes_skips_allergy_ingredients` (БД) — аллергия `peanuts` и свежий `milk` → `200` и в ответе только `["Milk soup"]` (рецепт с арахисом исключён).
- [x] `test_recommend_recipes_with_an_empty_fridge` (БД) — пустой холодильник → `200` и `{"recipes": []}`.
- [x] `test_recommend_recipes_rejects_a_token_of_an_unknown_user` (БД) — корректно подписанный токен с `sub = 424242` (пользователя нет) → `401`.

### `tests/test_user_preferences.py` — аллергии и предпочтения (9 кейсов)

- [x] `test_preferences_do_not_require_a_token` (контракт) — пустое тело → `400` (валидация срабатывает раньше доступа к БД, поэтому не `401`).
- `test_preferences_validation` (контракт) — группа из 6 кейсов, все ✅: некорректное тело → `400`:
  - [x] `[payload0]` нет `user_id`;
  - [x] `[payload1]` `user_id` строкой (`"1"`);
  - [x] `[payload2]` `user_id = 0`;
  - [x] `[payload3]` `allergies` строкой вместо списка;
  - [x] `[payload4]` в `allergies` есть не-строковый элемент (`42`);
  - [x] `[payload5]` в `preferences` есть строка из пробелов.
- [x] `test_preferences_are_persisted` (БД) — `POST /user_preferences` → `200` + `message`; значения проверены SQL-запросом к `users` (`allergies = ["peanuts"]`, `preferences = ["vegan"]`).
- [x] `test_preferences_for_unknown_user_are_rejected` (БД) — `user_id = 999999` → `400`, id указан в тексте ошибки.

### `tests/test_system.py` — системные пробы и контракт маршрутов (7 кейсов)

- [x] `test_index_returns_the_documented_greeting` (контракт) — `GET /` → `200`, `text/plain` и `Welcome to the recipe app!`.
- [x] `test_registered_routes_match_the_contract` (контракт) — `url_map` приложения совпадает с полным списком путей и методов из `openapi.yaml` (+ `/health`, `/ready`): 15 маршрутов, ни одного лишнего.
- [x] `test_health_is_ok_without_database` (контракт) — `GET /health` → `200` и `{"status": "ok"}` даже без доступной БД.
- [x] `test_ready_reports_missing_database` (контракт) — БД недоступна → `503` и `{"status": "not_ready", "database": "unavailable"}`.
- [x] `test_ready_reports_healthy_database` (БД) — БД доступна → `200` и `{"status": "ready", "database": "ok"}`.
- [x] `test_unknown_route_returns_error_object` (контракт) — `GET /no-such-endpoint` → `404` и тело с единственным ключом `error`.
- [x] `test_method_not_allowed_returns_error_object` (контракт) — `DELETE /login` → `405` и тело с единственным ключом `error`.

## Примечания для отчётности

- **Тесты, фиксирующие осознанные отклонения от CONTRIBUTION.md** (поведение задано `openapi.yaml`):
  `test_create_recipe_does_not_require_a_token`, `test_list_items_returns_items_of_every_user`,
  `test_preferences_do_not_require_a_token` — эти кейсы упадут, если маршруты решат закрыть токеном,
  поэтому при смене решения их нужно обновлять вместе с `openapi.yaml`.
- **Негативные кейсы против ограничений БД**: `[payload4]` в `test_fridge` (`quantity = 0`) и дубликаты
  email/username проверяют, что ограничения объявлены в самой схеме (`schema.sql`), а не только в коде.
- **Изоляция данных**: `test_delete_expired_touches_only_the_current_user` — единственный тест,
  доказывающий, что защищённый эндпоинт использует `user_id` из токена, а не из тела запроса.
- **Фикстуры** (`tests/conftest.py`): `app`/`client` — приложение без БД; `db_app`/`db_client` — приложение
  с БД и очисткой таблиц (`TRUNCATE ... RESTART IDENTITY CASCADE`); `register_user`, `auth_headers`,
  `add_fridge_items` — подготовка данных через реальные HTTP-запросы.
- **Результат последнего прогона**: 76 passed, 0 failed, 0 skipped — на живом PostgreSQL
  (проверено локально и в CI-workflow `Backend CI`).



