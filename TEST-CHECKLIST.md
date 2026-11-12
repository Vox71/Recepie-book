# Чек-лист тестов API

Приложение к отчёту `TASKS-REPORT.md`: полный перечень автоматических проверок backend
(`backend/tests/`, `pytest`) и того, что именно проверяет каждый кейс.

**Состав набора:** **151 кейс в 16 файлах**. 80 кейсов работают без базы (проверка входных
данных, работа с токеном, служебные адреса, сам контракт `openapi.yaml`, компоненты ML-модуля,
словарь аллергенов и его метрики, модель рекомендаций v1 и метрики ранжирования, разбор датасета
и CLI импорта, разбор страниц рецептов на сохранённых страницах), 71 — против реальной PostgreSQL
(включая саму схему БД, тела ответов, сверенные со схемами контракта, таймеры и обогащение
рецептов со страниц). На каждый адрес из
`openapi.yaml` приходится 1–3 кейса; адресов теперь 25 — три из них про избранное
(`/favorite_recipes`), три — про таймеры (`/timers`, `/timers/active`, `/timers/{id}`). Модуль
рекомендаций по-прежнему включается флагом
`SMART_RECOMMENDATIONS_ENABLED` внутри `GET /recommend_recipes`
(`tests/test_smart_recommendations.py`), а импорт датасета и обучение модели — это CLI, а не
новые маршруты.

## Как запускать

```bash
cd backend
python -m pytest                 # без БД: 80 passed, 71 skipped (DB-кейсы скипаются)
TEST_DATABASE_URL=postgresql://postgres:changeme@localhost:5432/mydatabase python -m pytest
                                 # с БД: 151 passed

# покрытие (statement + branch) и порог 80 %, см. docs/test-coverage.md
TEST_DATABASE_URL=postgresql://postgres:changeme@localhost:5432/mydatabase \
  coverage run -m pytest && coverage report
```

То же самое автоматически выполняет CI: workflow `Backend CI`
(`.github/workflows/backend-tests.yml`) поднимает PostgreSQL 15, запускает набор под `coverage`
на каждый push в `main` и на каждый pull request и падает, если покрытие ниже порога 80 %
(см. `[tool.coverage.report]` в `backend/pyproject.toml`).

## Итог последнего прогона

| Файл | Кейсов | Без БД | С БД | Тема |
|---|---|---|---|---|
| `tests/test_system.py` | 6 | 4 | 2 | служебные адреса, формат ошибок, лимит запросов (429) |
| `tests/test_auth.py` | 6 | 4 | 2 | регистрация, вход, проверка токена |
| `tests/test_recipes.py` | 11 | 0 | 11 | CRUD рецептов, пагинация списка, поля карточки рецепта, время приготовления, шаги/КБЖУ разобранного рецепта |
| `tests/test_favorites.py` | 4 | 0 | 4 | избранное: JWT, порядок, идемпотентность |
| `tests/test_fridge.py` | 7 | 1 | 6 | холодильник, пагинация списка и удаление просроченного, сериализация `last_added` |
| `tests/test_user_preferences.py` | 2 | 1 | 1 | аллергии и предпочтения |
| `tests/test_notifications_recommendations.py` | 6 | 1 | 5 | уведомления и рекомендации |
| `tests/test_database.py` | 11 | 0 | 11 | схема БД, ограничения, триггеры, таблицы без адресов |
| `tests/test_importer_povarenok.py` | 12 | 9 | 3 | импорт датасета: разбор, форматы, идемпотентность, CLI и точка входа `python -m app.importer` |
| `tests/test_ml_engine.py` | 2 | 2 | 0 | компоненты ML-модуля: предобработка, KNN, бонус холодильника |
| `tests/test_smart_recommendations.py` | 3 | 0 | 3 | `GET /recommend_recipes` с флагом и без него |
| `tests/test_allergens.py` | 16 | 13 | 3 | словарь аллергенов, ложные срабатывания, метрики, фильтр по `recipe_ingredients`, границы фильтра |
| `tests/test_recommendation_model.py` | 9 | 8 | 1 | модель v1: веса IDF, артефакт, откат на заглушку, метрики ранжирования, CLI |
| `tests/test_openapi_contract.py` | 22 | 17 | 5 | сам контракт: валидность по спецификации, маршруты и лимиты из файла, тела реальных ответов по схемам (включая таймеры и разобранный рецепт) |
| `tests/test_timers.py` | 11 | 1 | 10 | таймеры: время рецепта, дедлайн из базы, список активных, изоляция по токену, отмена, лимиты |
| `tests/test_importer_pages.py` | 23 | 19 | 4 | разбор страницы povarenok: шаги, время, порции, КБЖУ, cp1251, ошибки сети, кэш, идемпотентность обогащения |
| **Всего** | **151** | **80** | **71** | |

Проверено 12.11.2026 на ветке `feat/recipe-pages`: без БД — `80 passed, 71 skipped`
(exit 0); с реальной PostgreSQL 15 (контейнер Docker) — `151 passed, 0 skipped` (exit 0);
`ruff check .` и `black --check .` — без замечаний. Покрытие того же прогона: **88,7 % строк**
и **82,5 % ветвей** (порог 80 %, подробности — `docs/test-coverage.md`). Те же 151 кейс повторяет
CI на PostgreSQL 15: там доступность базы контролируется отдельным шагом, поэтому набор не может
«позеленеть» на одних пропусках.

## Покрытие эндпоинтов: 25 адресов, 1–3 кейса на адрес

| Адрес | Кейсы | Что проверяется |
|---|---|---|
| `GET /` | `test_index_returns_the_greeting` | 200 и текст приветствия из контракта |
| `GET /health` | `test_health_is_ok_without_a_database` | 200 `{"status":"ok"}` без обращения к БД |
| `GET /ready` | `test_ready_reports_a_missing_database`, `test_ready_reports_a_healthy_database` | 503 «база недоступна» и 200 «база ok» |
| `POST /register` | `test_register_creates_a_user`, `test_register_rejects_invalid_payloads` | 201 + пароль scrypt-хэшем + нормализация аллергий + отказ на дубликаты; 400 на 9 «плохих» тел и не-JSON |
| `POST /login` | `test_login_returns_a_token`, `test_login_requires_email_and_password` | 401 на неверный пароль и неизвестный email, 200 + `token`; 400 без email/password |
| `GET /protected` | `test_protected_accepts_a_valid_token`, `test_protected_rejects_bad_tokens` | 200 с `user_id` из токена; 401 в 6 вариантах (нет заголовка, чужая схема, пустой/битый/просроченный токен, без `sub`) |
| `POST /user_preferences` | `test_preferences_are_stored_normalized_and_cleared`, `test_user_preferences_validation` | 200 + запись в `users` и `user_allergy_preferences` (замена без дублей, очистка), 400 на неизвестный `user_id`; 400 на 6 некорректных тел |
| `GET /recipes` | `test_list_recipes_returns_every_recipe`, `test_list_recipes_returns_one_page`, `test_list_recipes_validates_the_pagination` | 200, список рецептов без удалённого `cuisine_type`; страницы `limit`/`offset`, сортировка по id; 400 на 7 некорректных `limit`/`offset` |
| `POST /recipes` | `test_create_recipe_stores_it_under_the_database_column_names`, `test_create_recipe_validates_the_payload` | 201 + запись в колонки `recipe_name`/`instruction`; 400 на 8 некорректных тел |
| `GET /recipes/{id}` | `test_get_recipe_by_id` | 200 с телом рецепта, 404 на неизвестный id |
| `PUT /recipes/{id}` | `test_update_recipe` | 200, изменение сохранено; 400 на неполное тело, 404 на неизвестный id |
| `DELETE /recipes/{id}` | `test_delete_recipe` | 200, рецепт исчез из списка; 404 на неизвестный id |
| `GET /favorite_recipes` | `test_add_list_and_remove_favourites`, `test_favourites_validate_the_recipe_id_and_the_pagination` | 200, только избранное владельца токена, от новых к старым; 401 без токена; 400 на `limit`/`offset` |
| `POST /favorite_recipes` | `test_add_list_and_remove_favourites`, `test_favourite_routes_require_a_token`, `test_favourites_validate_the_recipe_id_and_the_pagination` | 201 и сообщение, повтор идемпотентен (дубля нет), `user_id` из тела игнорируется; 400 на 7 некорректных тел, 404 на неизвестный рецепт, 401 без токена |
| `DELETE /favorite_recipes/{id}` | `test_add_list_and_remove_favourites`, `test_favourites_of_another_user_are_invisible` | 200 и запись исчезла; чужая запись → 404, у владельца остаётся; 401 без токена |
| `GET /fridge_items` | `test_add_and_list_fridge_items`, `test_list_fridge_items_returns_one_page`, `test_list_fridge_items_validates_the_pagination` | 200, поля продукта, `id` = `fridge_items.item_id`; страницы `limit`/`offset` с порядком по `expiration_date`/`item_id`; 400 на 7 некорректных значений |
| `POST /fridge_items` | `test_add_and_list_fridge_items`, `test_add_fridge_items_validates_the_payload` | 201 + сохранение батча; 400 на 10 некорректных тел (включая `quantity = 0` и неизвестного пользователя) |
| `DELETE /delete_expired_products` | `test_delete_expired_products_removes_only_expired_items`, `test_delete_expired_products_uses_the_database_date_as_the_boundary` | удаляются только просроченные; граница «вчера / сегодня / завтра» по дате БД; повторный вызов безопасен |
| `GET /notify_expired` | `test_notify_expired_lists_only_expired_products`, `test_notify_expired_and_delete_expired_products_use_one_rule` | пустой холодильник и список просроченных продуктов; отчёт и удаление считают просроченным одно и то же |
| `DELETE /delete_expired` | `test_delete_expired_touches_only_the_user_from_the_token` | удаляются продукты только того пользователя, чей токен, по тому же правилу |
| `GET /suggest_recipes` | `test_suggest_recipes_uses_the_expired_products` | подсказки по просроченным продуктам + запись в `generated_recipes` |
| `GET /recommend_recipes` | `test_recommend_recipes_uses_the_fridge_and_skips_the_allergies` | рекомендации по холодильнику без аллергенов, история выдачи, пустой холодильник, аллергии из текстовой колонки |
| `POST /timers` | `test_a_timer_is_created_from_the_recipe_time`, `test_a_recipe_without_cooking_time_requires_a_duration`, `test_timer_payloads_are_validated`, `test_a_timer_requires_an_existing_recipe` | 201 + дедлайн `started_at + duration` по часам базы; длительность из `cooking_time_minutes`; 400 на неверные тела и рецепт без времени; 404 на неизвестный рецепт |
| `GET /timers/active` | `test_an_active_timer_survives_a_reload`, `test_an_expired_timer_is_closed_lazily`, `test_the_active_timers_are_ordered_and_capped` | список с `server_time` и `remaining_seconds`, порядок по дедлайну, истёкшие закрываются чтением, лимит 20 |
| `DELETE /timers/{id}` | `test_cancel_removes_the_timer_from_active`, `test_timers_are_isolated_by_the_token` | 200 и исчезновение из активных; повторная отмена и чужой таймер → 404 |

## Что проверяет каждый файл

### `tests/test_system.py` — 6 кейсов (4 без БД)

- [x] `test_index_returns_the_greeting` — `GET /` → 200, `text/plain`, точный текст приветствия.
- [x] `test_health_is_ok_without_a_database` — liveness-проба работает без базы (200).
- [x] `test_ready_reports_a_missing_database` — readiness-проба без базы → 503 `{"database":"unavailable"}`.
- [x] `test_ready_reports_a_healthy_database` — с базой → 200 `{"database":"ok"}`.
- [x] `test_unknown_address_and_method_return_an_error_object` — 404 и 405 отдают единый
  формат ошибки `{"error": "..."}`.
- [x] `test_rate_limit_blocks_the_third_registration` (БД) — с `RATE_LIMIT_ENABLED=true` и
  `RATE_LIMIT_MAX_REQUESTS=2` третий `POST /register` с того же IP получает 429 и обычный
  объект ошибки, а запрос с другим `X-Forwarded-For` (прокси) проходит: лимит считается по
  клиенту, а не по процессу.

### `tests/test_auth.py` — 6 кейсов (4 без БД)

- [x] `test_register_creates_a_user` — 201; в БД попадает scrypt-хэш (162 символа, влезает в
  `varchar(200)`), аллергии и предпочтения сохраняются и текстом в `users`, и строками в
  `user_allergy_preferences`; повторный email и повторный username → 400.
- [x] `test_register_rejects_invalid_payloads` — 400 в цикле на 9 некорректных тел
  (пустое тело, нет password, плохой email, короткий пароль, пустой username, слишком длинные
  username/email/аллергия, аллергии не списком) + не-JSON тело.
- [x] `test_login_returns_a_token` — неверный пароль → 401, неизвестный email → 401,
  верные данные → 200 и непустой `token`.
- [x] `test_login_requires_email_and_password` — 400, если не переданы email или password.
- [x] `test_protected_accepts_a_valid_token` — 200, `user_id` строкой (как в контракте).
- [x] `test_protected_rejects_bad_tokens` — 401 в 6 вариантах: нет заголовка, не Bearer,
  пустой токен, не JWT, просроченный токен, токен без `sub`.

### `tests/test_recipes.py` — 11 кейсов (все с БД)

- [x] `test_create_recipe_stores_it_under_the_database_column_names` — 201 и запись в колонки
  `recipe_name`, `ingredients`, `instruction`, `difficulty_level` (API-поля `name`/`instructions`
  переводятся сериализатором).
- [x] `test_create_recipe_validates_the_payload` — 400 на 8 тел: нет одного из четырёх
  обязательных полей, не строка, значения длиннее допустимого (`200`/`10000`/`50` символов);
  инструкция в 5 000 символов, наоборот, принимается с 201 (`recipes.instruction` — `text`).
- [x] `test_list_recipes_returns_every_recipe` — 200, оба созданных рецепта в списке,
  `id` — целое, `cuisine_type` больше не отдаётся.
- [x] `test_list_recipes_returns_one_page` — 5 рецептов: без параметров приходят все (лимит по
  умолчанию 50), `?limit=2&offset=1` — ровно второй и третий по порядку id, `?offset=4` —
  последний, `?offset=10` — пустой массив.
- [x] `test_list_recipes_validates_the_pagination` — 400 на 7 значений (`limit=0`, `-1`, `abc`,
  `201`; `offset=-1`, `abc`, `1000001`) и 200 на граничном `limit=200&offset=0`.
- [x] `test_get_recipe_by_id` — 200 с полным телом рецепта (все восемь полей `Recipe`, у ручного
  рецепта `ingredient_list` пуст, `source_url` и `cooking_time_minutes` = `null`); неизвестный id → 404.
- [x] `test_imported_recipe_exposes_the_source_and_the_ingredient_list` — рецепт «как из импортёра»
  (заполнен `source_url`, нет инструкции и сложности, строки `recipe_ingredients` вставлены не по
  порядку): ответ содержит ровно поля `Recipe`, `instructions`/`difficulty_level` = `null`,
  `source_url` = ссылка на источник, `ingredient_list` отсортирован по `sort_order` и сохраняет
  `quantity = null` у продукта без количества; та же структура приходит и в странице `GET /recipes`.
- [x] `test_a_recipe_declares_its_cooking_time` — `cooking_time_minutes` необязательное поле
  `RecipeInput`: с ним рецепт отдаёт значение и в списке, и в БД; без него — `null` (у импортированных
  рецептов времени нет); 400 на `0`, `1441`, строку, `true` и дробное; `PUT` умеет и перезаписать,
  и обнулить.
- [x] `test_a_parsed_recipe_exposes_steps_servings_and_nutrition` — разобранный рецепт отдаёт
  `servings`, `steps` (номер, текст, фото; `null`, если фото нет) и `nutrition` (8 чисел + `source`)
  и в карточке, и в странице списка: объект `Recipe` одинаков на всех адресах.
- [x] `test_update_recipe` — 200, изменённые поля сохранены (остальные не потеряны);
  неполное тело → 400, неизвестный id → 404.
- [x] `test_delete_recipe` — 200, рецепт исчез, список пуст; повторное удаление → 404.

### `tests/test_favorites.py` — 4 кейса (все с БД)

- [x] `test_add_list_and_remove_favourites` — 201 и сообщение при добавлении; повторное
  добавление дубля не создаёт и отвечает 201 «уже в избранном»; `user_id` в теле игнорируется
  (избранное принадлежит владельцу токена); список отдаёт рецепты от новых к старым; `DELETE`
  убирает запись.
- [x] `test_favourite_routes_require_a_token` — 401 на все три адреса без заголовка и на битый токен.
- [x] `test_favourites_of_another_user_are_invisible` — второй пользователь видит пустой список,
  чужая запись при `DELETE` → 404, строка владельца остаётся.
- [x] `test_favourites_validate_the_recipe_id_and_the_pagination` — 400 на 7 тел (`recipe_id`
  нет, `0`, `-1`, строка, дробное, `true`, тело-массив), 404 на неизвестный рецепт, 400 на
  `limit=0` и `offset=abc`, 200 на `limit=200`.

### `tests/test_fridge.py` — 7 кейсов (1 без БД)

- [x] `test_serializers_render_missing_values_and_keep_the_utc_offset` — `serialize_fridge_item`:
  `NULL`-дата и `NULL`-количество остаются `null`, «голая» метка времени
  (`timestamp` без зоны) выходит как `2026-11-12T10:30:00+00:00` — так выполняется
  `format: date-time` контракта; `iso_date(None)` и `iso_datetime(None)` дают `None`.
- [x] `test_add_and_list_fridge_items` — 201 и сообщение `N fridge item(s) added`; в списке
  корректные поля, `id` ответа совпадает с `fridge_items.item_id`, `quantity` — целое.
- [x] `test_list_fridge_items_returns_one_page` — три продукта: без параметров приходят все
  (лимит по умолчанию 50), `?limit=1&offset=1` — второй по порядку, `?offset=2` — последний,
  `?offset=3` — пустой массив.
- [x] `test_list_fridge_items_validates_the_pagination` — 400 на 7 значений (`limit=0`, `-1`,
  `abc`, `201`; `offset=-1`, `abc`, `1000001`) и 200 на граничном `limit=200&offset=0`.
- [x] `test_add_fridge_items_validates_the_payload` — 400 в цикле на 10 тел: тело не массив,
  пустой массив, элемент не объект, пустой объект, нет `quantity`, `quantity = 0` (CHECK в схеме),
  дробное `quantity`, длинное имя продукта, дата не в ISO 8601, несуществующий `user_id`.
- [x] `test_delete_expired_products_removes_only_expired_items` — удаляется только просроченный
  продукт, продукт со сроком «сегодня» остаётся; повторный вызов удаляет 0 и не падает.
- [x] `test_delete_expired_products_uses_the_database_date_as_the_boundary` — продукты с датами
  `CURRENT_DATE - 2`, `CURRENT_DATE - 1`, `CURRENT_DATE`, `CURRENT_DATE + 1` (созданы через
  фикстуру `add_relative_fridge_items`, то есть по тем же часам, что и правило): удаляются ровно
  два просроченных, «сегодня» и «завтра» остаются, дата «сегодня» совпадает с `CURRENT_DATE`;
  повторный `DELETE` → 0.

### `tests/test_timers.py` — 11 кейсов (1 без БД)

Спринт 3, задача 1: таймер в рецепте. Проверяется то, что можно проверить на сервере — дедлайн,
изоляция по токену, состояния; точность отрисовки — свойство алгоритма из `docs/timer.md` §5.

- [x] `test_a_timer_is_created_from_the_recipe_time` — без `duration_seconds` сервер берёт
  `cooking_time_minutes × 60` (2 мин → 120 с); `label` по умолчанию — название рецепта; в ответе
  ровно поля `Timer`; `ends_at − started_at = 120 с`; `server_time ≤ ends_at`.
- [x] `test_a_recipe_without_cooking_time_requires_a_duration` — у рецепта без времени 400 с
  текстом «has no cooking time»; с явными `duration_seconds` таймер создаётся.
- [x] `test_a_timer_requires_an_existing_recipe` — нет `recipe_id` или он `0` → 400; неизвестный
  рецепт → 404; тело не объект → 400; `label` обрезается по краям, явная длительность важнее
  времени рецепта.
- [x] `test_the_deadline_is_started_at_plus_duration` — в БД `ends_at − started_at = 90 с`,
  `ends_at` ещё в будущем, `status = running`, `closed_at` пуст: время считает база, а не Python.
- [x] `test_timers_are_isolated_by_the_token` — второй пользователь не видит чужой таймер и
  получает 404 на его отмену; владелец по-прежнему видит свой.
- [x] `test_an_active_timer_survives_a_reload` — повторный `GET /timers/active` отдаёт тот же
  `ends_at` и `server_time` (точка отсчёта для восстановления), `remaining_seconds` не растёт.
- [x] `test_an_expired_timer_is_closed_lazily` — после сдвига `ends_at` в прошлое список пуст,
  в БД `status = finished` и `closed_at = ends_at` (а не «когда заметили»); отменить его уже нельзя.
- [x] `test_cancel_removes_the_timer_from_active` — `DELETE` → 200, из активных исчез,
  повторная отмена → 404, в БД `cancelled`.
- [x] `test_the_active_timers_are_ordered_and_capped` — порядок по дедлайну (100, 200, 300 с);
  после 20 активных 21-й → 400 «at most 20 timers can run at once».
- [x] `test_timer_payloads_are_validated` — 400 на `duration_seconds` 0, 86401, `"10"`, `true`,
  `label` из 101 символа и `recipe_id` строкой; граничные 86 400 с принимаются.
- [x] `test_timers_require_a_token` — 401 на всех трёх адресах без токена.

### `tests/test_user_preferences.py` — 2 кейса (1 без БД)

- [x] `test_preferences_are_stored_normalized_and_cleared` — 200; значения попадают в
  `users.allergies`/`preferences` текстом и в `user_allergy_preferences` строками; повторный
  вызов заменяет старые значения без дублей; пустой список очищает и то, и другое;
  неизвестный `user_id` → 400.
- [x] `test_user_preferences_validation` — 400 в цикле на 6 тел (нет `user_id`, `user_id`
  строкой или нулём, аллергии не списком, элементы не строки, пустые элементы).

### `tests/test_notifications_recommendations.py` — 6 кейсов (1 без БД)

- [x] `test_all_four_routes_require_a_token` — 401 для `/notify_expired`, `/delete_expired`,
  `/suggest_recipes`, `/recommend_recipes` без токена и с испорченным токеном.
- [x] `test_notify_expired_lists_only_expired_products` — пустой холодильник → сообщение
  `No expired products found`; с продуктами → в `expired_products` только просроченный.
- [x] `test_notify_expired_and_delete_expired_products_use_one_rule` — отчёт `GET /notify_expired`
  и удаление `DELETE /delete_expired_products` считают просроченным один и тот же набор: сколько
  продуктов попало в отчёт, столько же удалено; продукт со сроком «сегодня» остаётся; после
  удаления отчёт пуст.
- [x] `test_delete_expired_touches_only_the_user_from_the_token` — удаляются продукты того
  пользователя, чей токен; данные второго пользователя остаются.
- [x] `test_suggest_recipes_uses_the_expired_products` — без просроченных продуктов рецептов нет;
  с просроченным молоком предлагается только рецепт с молоком, и выдача записана в
  `generated_recipes`.
- [x] `test_recommend_recipes_uses_the_fridge_and_skips_the_allergies` — рецепт с аллергеном
  исключён, рецепт из холодильника рекомендован и записан в `generated_recipes`; пустой
  холодильник → пустой список; аллергии, записанные в `users.allergies` напрямую (без строк в
  `user_allergy_preferences`), тоже учитываются.

### `tests/test_smart_recommendations.py` — 3 кейса (все с БД)

Кейсы прогоняют один и тот же набор данных дважды: второе приложение собирается фабрикой
`db_app_factory` (`conftest.py`) с `SMART_RECOMMENDATIONS_ENABLED=true` и работает с той же
базой — так проверяется, что флаг действительно переключает логику адреса.

- [x] `test_the_flag_on_ranks_the_favourites_and_the_fridge` — флаг включён: 4 рецепта, избранное
  (Milk soup + Tomato salad), в холодильнике молоко, аллергия на арахис. Ответ 200:
  `Milk soup` (похож на избранное и есть молоко), `Tomato salad` (похож на профиль без продукта
  из холодильника), `Milk porridge`; `Peanut cookies` отброшен фильтром аллергенов, `id` ответа
  совпадают с `recipes`, тело состоит ровно из `message` + `recipes` (внутренние оценки наружу
  не утекают), сообщение содержит `rejected by allergy`, в `generated_recipes` 3 строки.
- [x] `test_the_flag_off_keeps_the_baseline_answer` — флаг выключен: на тех же данных ответ
  `Milk soup` + `Milk porridge` — базовая логика про избранное не знает, поэтому поведение
  адреса не изменилось.
- [x] `test_smart_mode_answers_an_empty_profile_and_rejects_an_unknown_user` — без избранного и
  без холодильника 200 и пустой `recipes` с сообщением; токен удалённого пользователя → 401
  `{"error": "User from the token does not exist"}`.

### `tests/test_allergens.py` — 16 кейсов (13 без БД)

Файл про задачу 6.1: словарь аллергенов `app/ml/allergens.py`, скрипт метрик
`app/ml/allergen_eval.py` и фильтр `app/services/allergen_service.py`. Покрытие этих двух
модулей фильтра — 100 % строк и 100 % ветвей (задача 7, `docs/test-coverage.md`).

- [x] `test_every_group_and_alias_points_at_a_known_group` — 13 групп, у каждой есть термин,
  `slug` совпадает с ключом, каждая запись `ALLERGEN_ALIASES` ведёт в существующую группу.
- [x] `test_allergy_terms_resolve_into_groups_or_stay_plain_terms` — «молочные продукты» → `milk`,
  «КРЕВЕТКИ» → `seafood` (регистр не важен), «gluten» → `gluten`; «кокос» и «киви» остаются
  обычными терминами, пустой профиль не отбрасывает ничего.
- [x] `test_matching_finds_word_forms_synonyms_and_phrases` — 32 продукта в разных формах:
  «Сливки 10%», «Яичный белок», «Масло сливочное» (в отличие от «Масло растительное»),
  «Соевый соус» → `soy` + `gluten`, «Икра красная» → `fish`, английские `Butter`, `Soy sauce`.
- [x] `test_lookalikes_do_not_trigger_unrelated_allergens` — 23 «похожих, но не аллергена»:
  кокос (и кокосовое молоко), гречка и гречневая мука, рисовая и кукурузная мука, мускатный
  орех, «картофель сырой», печень, икра кабачковая, томатная паста, безглютеновый хлеб,
  соевый и растительный белок, `coconut milk`, `buckwheat flour`, `eggplant`, `nutmeg`.
- [x] `test_custom_allergy_term_is_matched_by_lemma` — аллергия, которой нет в словаре
  («киви»), всё равно фильтрует рецепты по лемме.
- [x] `test_repeated_allergy_terms_resolve_once` — «молочные продукты» и «молоко» дают одну
  группу, «КРЕВЕТКИ» и `seafood` — тоже; повтор одного и того же неизвестного термина не
  дублирует его в запросе.
- [x] `test_a_stop_word_allergy_stays_a_plain_term` — аллергия из стоп-слова («без») не имеет
  леммы: она остаётся обычным термином и ничего не отбрасывает (защита от «тихой» потери
  аллергии).
- [x] `test_matching_ignores_an_empty_or_punctuation_only_ingredient` — пустой список, строки из
  пробелов и «!!!» ничего не находят и не ломают фильтр; продукт рядом с ними по-прежнему
  находится.
- [x] `test_is_safe_answers_the_opposite_of_matched_allergens` — `is_safe` = «нет совпадений»:
  «кокосовое молоко» безопасно для аллергии на молоко, «молоко» — нет, пустой запрос безопасен.
- [x] `test_a_dictionary_term_without_lemmas_is_skipped` — защитная ветка словаря: термин из
  стоп-слов не превращается в пустое правило, остальные термины группы продолжают совпадать
  (используется синтетическая группа, у настоящих групп таких терминов нет).
- [x] `test_ingredient_names_falls_back_to_the_text_when_a_row_has_no_id` — рецепт без `id`
  (не из базы) и рецепт без строк `recipe_ingredients` проверяются по тексту `ingredients`.
- [x] `test_labelled_sample_has_no_missed_allergens` — размеченная выборка из 211 рецептов:
  `violation_rate = 0`, `F1 >= 0.95`, каждая группа встречается хотя бы раз, расхождений нет.
- [x] `test_metrics_count_a_missed_allergen` — на синтетическом примере видно, что пропущенный
  аллерген даёт `false_negatives = 1`, `recall = 0.5`, `violation_rate = 0.5` и попадает в список
  расхождений.
- [x] `test_the_filter_reads_recipe_ingredients_instead_of_the_text` (БД) — рецепт с текстом
  «рис, вода» и строкой `recipe_ingredients` «Молоко» отбрасывается, а рецепт с текстом
  «молоко» и строкой «Кокосовое молоко» остаётся; рецепт без строк ингредиентов проверяется
  по тексту, пустой профиль аллергий не отбрасывает ничего.
- [x] `test_recommendations_exclude_a_recipe_hidden_by_its_normalized_ingredients` (БД) —
  `GET /recommend_recipes` отдаёт только безопасный суп, хотя в тексте «молочного» супа тоже
  есть продукт из холодильника.
- [x] `test_smart_recommendations_filter_by_the_normalized_ingredients` (БД) — то же для
  `SMART_RECOMMENDATIONS_ENABLED=true`: движок получает строки `recipe_ingredients`, в
  сообщении остаётся «1 rejected by allergy».


### `tests/test_ml_engine.py` — 2 кейса (без БД)

Юнит-тесты самого модуля (`app/ml`) — без Flask и без базы, поэтому идут в любом окружении.

- [x] `test_preprocessing_normalizes_lemmatizes_and_marks_allergens` — компонент 1:
  `МолОко, ЯЙЦА!` → `молоко яйца`, стоп-слова убираются, разные формы одного продукта дают одну
  лемму (`яйца`/`яйцо`, `молока`/`молоко`, `печенье`/`печенья`, `peanuts`/`peanut`,
  `tomatoes`/`tomato`), аллерген `peanut` находится в `peanuts`, аллергия из двух слов
  (`peanut butter`) — только при полном совпадении, чужой аллерген не срабатывает.
- [x] `test_knn_and_the_engine_rank_by_similarity_and_fridge_products` — компоненты 4–6: порядок
  KNN по косинусной близости, одинаковая близость сохраняет исходный порядок (ответ
  детерминирован), рецепт с аллергеном отброшен (`rejected_by_allergy = 1`), бонус за
  холодильник поднимает молочные рецепты, `limit` ограничивает ответ, «холодный старт» без
  избранного строит профиль по холодильнику и не добивает список рецептами с нулевой оценкой.

### `tests/test_recommendation_model.py` — 9 кейсов (8 без БД)

Модель рекомендаций v1 (задачи 6.0 и 6.2): артефакт TF-IDF, откат на заглушку и метрики
ранжирования. Числа прогона — в `docs/recommendation-model.md`.

- [x] `test_fit_weights_rare_lemmas_above_common_ones` — `idf = ln((1+N)/(1+df)) + 1`: редкая
  лемма весит больше частой (`sugar > rice > milk` для корпуса из четырёх рецептов), незнакомое
  слово получает `default_idf` (наибольший вес), повтор продукта в тексте вес не удваивает,
  пустой корпус — `ValueError`.
- [x] `test_artifact_round_trip_and_the_stat_cache` — `save` создаёт каталог и пишет JSON с
  `version`/`documents`/`source`; `load` возвращает те же веса; `load_cached` отдаёт тот же
  объект из кэша и перечитывает файл после перезаписи (переобучение без рестарта).
- [x] `test_missing_or_broken_artifact_keeps_the_bag_of_lemmas_fallback` — критерий приёмки:
  отсутствующий файл, битый JSON, чужая версия и пустой словарь весов → `None`, сервис работает
  на bag-of-lemmas; `SMART_RECOMMENDATIONS_ARTIFACT` попадает в настройки.
- [x] `test_engine_ranks_with_the_model_when_the_artifact_exists` (2 параметра) — с артефактом
  `vectorizer=tf-idf-v1`, `model_documents=3` и первым идёт рецепт с редким шафраном; без
  артефакта — `sparse-bow`, `model_documents=None` и прежний порядок (первым рис).
- [x] `test_leave_one_ingredient_out_protocol_counts_every_metric` — арифметика протокола на
  корпусе с известным ответом: из шести возможных запросов посчитаны четыре, два пропущены
  (продукт есть только в исходном рецепте), `P@1 = R@5 = Hit@5 = MRR = 1.0`, `P@5 = 0.2`,
  разбивка по частоте — группа `rare`.
- [x] `test_v1_is_better_than_the_baseline_on_the_committed_corpus` — критерий задачи на корпусе
  репозитория (120 рецептов): `P@5` и `MRR` у v1 выше, `Hit@5` не ниже.
- [x] `test_cli_prints_the_numbers_and_gates_a_regression` — `python -m app.ml.model` пишет
  артефакт, `python -m app.ml.evaluate` печатает таблицу и вердикт; на корпусе без выигрыша
  код возврата 1 (если не передан `--allow-regression`), на отсутствующем файле — 1.
- [x] `test_the_corpus_is_read_from_the_database` (БД) — `corpus.from_database`: имена берутся из
  `recipe_ingredients`, рецепт без ингредиентов пропускается, текстовая колонка работает как
  запасной вариант.

### `tests/test_importer_pages.py` — 23 кейса (19 без БД)

Спринт 3, задача 2: разбор страницы povarenok.ru и обогащение импортированных рецептов. Все кейсы
офлайновые: страницы лежат в `tests/data/pages/*.html` (реальная разметка, обрезанная до нужных
блоков), сеть подменяется подставным `opener`, как в `test_importer_povarenok.py`.

- [x] `test_parse_full_page` — страница со шагами, временем, порциями и КБЖУ: имя, 7 шагов,
  время 40 минут, 6 порций, 12 ингредиентов, 3 категории, описание, фото у каждого шага,
  нумерованный `instruction_text` (`1. …\n2. …`).
- [x] `test_nutrition_of_the_full_page` — две группы таблицы («Готового блюда» и «100 г блюда»)
  раскладываются в восемь чисел.
- [x] `test_a_page_without_time_and_servings` — время и порции `None`, остальное разбирается.
- [x] `test_a_page_without_steps_and_nutrition` — пустые `steps`/`nutrition` и `instruction_text
  is None` — это не ошибка.
- [x] `test_step_text_keeps_the_line_breaks_of_the_source` — `<br>` источника остаётся переводом
  строки внутри шага, а не создаёт новый шаг.
- [x] `test_cooking_time_is_read_from_the_microdata` (6 параметров) — `PT40M` → 40,
  `PT1H20M` → 80, `PT90M` → 90, текст «1 час 20 минут» → 80, `PT3D` → `None` (вне 1..1440),
  «много» → `None`.
- [x] `test_a_page_without_microdata_is_rejected` — не рецепт → `PageError` «no microdata».
- [x] `test_a_page_with_microdata_but_no_name_is_rejected` — только `nutrition` без имени и шагов
  → `PageError` «not a recipe page».
- [x] `test_broken_markup_does_not_crash_the_parser` — незакрытые `<li>` не роняют парсер: текст
  сохраняется как шаги.
- [x] `test_fetch_decodes_windows_1251_and_identifies_itself` — cp1251 декодируется, `User-Agent`
  начинается с `RecepieBookBot/`, таймаут передаётся в `opener`.
- [x] `test_fetch_turns_http_error_into_page_error` — 403 → `PageError` с «HTTP 403».
- [x] `test_fetch_turns_network_error_into_page_error` — таймаут сети → `PageError`, не `URLError`.
- [x] `test_page_summary_describes_the_page` — сводка для `--url`/`--dry-run` готова к `json.dumps`.
- [x] `test_enrich_saves_the_parsed_page` (БД) — шаги, время, порции, КБЖУ, `parsed_at` и
  `parser_version = pages/1` попадают в базу; фото шага сохранено.
- [x] `test_enrich_marks_a_page_without_steps` (БД) — строк шагов нет, но рецепт помечен
  разобранным, чтобы не тянуть его снова; счётчик `without_steps`.
- [x] `test_enrich_is_idempotent_and_uses_the_cache` (БД) — второй прогон: `candidates = 0`;
  `--force` перезаписывает, но берёт страницу из кэша (сеть запрещена подставным `opener`).
- [x] `test_enrich_counts_a_failed_page_and_keeps_going` (БД) — 404 одной страницы не мешает
  обогатить вторую, «сломанная» остаётся `parsed_at IS NULL`.
- [x] `test_load_page_reports_where_the_html_came_from` — кэш пишется при первом вызове и
  используется при втором (один запрос на страницу).

### `tests/test_database.py` — 11 кейсов (все с БД)

Файл — «исполняемая» копия схемы `docs/db_scheme.png` (с расширениями из `docs/db_schema.md`)
и проверка того, что не покрыто адресами.

- [x] `test_tables_columns_and_primary_keys_match_the_diagram` — ровно 10 таблиц, у каждой
  колонки тип и длина как на диаграмме, первичные ключи совпадают; `cuisine_type` отсутствует.
- [x] `test_foreign_keys_and_the_email_index_match_the_diagram` — все внешние ключи и правила
  `ON DELETE` (`CASCADE`/`SET NULL`), уникальный индекс `lower(email)` (email без учёта регистра).
  Определение индекса сравнивается после нормализации: PostgreSQL печатает `lower(email)` как
  `lower((email)::text)`, поэтому функция `_normalized_index_definition` убирает приведение типа
  и лишние скобки.
- [x] `test_triggers_and_functions_of_the_fridge_history_exist` — на `fridge_items` висят два
  триггера и существуют их функции.
- [x] `test_database_constraints_are_enforced` — ограничения работают на уровне БД:
  `CHECK (quantity > 0)`, `NOT NULL` для пароля, уникальность username и email (без учёта регистра).
- [x] `test_fridge_history_records_the_insert_and_the_update` — добавление продукта создаёт
  версию 1 и запись `INSERT` без старых значений; изменение → версия 2 и запись `UPDATE`
  со старым и новым значением.
- [x] `test_fridge_history_survives_the_delete_of_a_product_and_of_a_user` — удаление
  просроченного продукта пишет `DELETE`, история версий остаётся (ссылка обнуляется);
  удаление пользователя чистит каскадом продукты, аллергии и аудит, но не ломает триггер
  и сохраняет историю версий.
- [x] `test_favorite_recipes_are_unique_and_cascade` — `favorite_recipes`: добавление, проверка,
  список, повторное добавление игнорируется, несуществующий рецепт отклоняется внешним ключом,
  снятие, удаление рецепта убирает его из избранного (`app.models` напрямую: так проверяются
  уникальность пары и каскад, на которые опираются маршруты `/favorite_recipes`).
- [x] `test_generated_recipes_keep_what_was_offered` — `generated_recipes`: запись выдачи,
  пустая выдача ничего не пишет, несуществующий рецепт отклоняется, очистка истории,
  каскад при удалении рецепта.
- [x] `test_recipe_ingredients_are_unique_and_cascade` — `recipe_ingredients`: ингредиенты
  рецепта с количеством и порядком, `NULL` в количестве допустим, повтор ингредиента в одном
  рецепте отклоняется, тот же ингредиент в другом рецепте разрешён, несуществующий рецепт
  отклоняется внешним ключом, удаление рецепта чистит только его ингредиенты.
- [x] `test_imported_recipes_are_unique_by_source_url` — `recipes.source_url`: два рецепта с
  одним url отклоняются, у ручных рецептов `source_url IS NULL` и таких строк может быть
  сколько угодно, повторная вставка с `ON CONFLICT (source_url) DO NOTHING` ничего не пишет
  (идемпотентность импорта).
- [x] `test_recipe_timestamps_and_the_text_instruction_are_maintained_by_the_database` —
  `created_at`/`updated_at` заполняются базой, триггер `recipes_updated_at_trigger` двигает
  `updated_at` при `UPDATE` и не трогает `created_at`, инструкция длиннее 100 символов
  сохраняется целиком (колонка `text`), у импортированного рецепта `instruction`,
  `difficulty_level` и `source_url` равны `NULL`.

### `tests/test_importer_povarenok.py` — 12 кейсов (9 без БД)

Сырые данные датасета не коммитятся (лицензия не указана), поэтому кейсы используют синтетический
сэмпл `tests/data/povarenok_sample.json` (12 рецептов, 60 строк ингредиентов) и маленькие файлы,
которые тест пишет во временную папку `tmp_path`. Сеть не используется: скачивание проверяется
подставным `opener`.

- [x] `test_record_from_row_normalizes_the_dataset_values` — пробелы и неразрывный пробел
  схлопываются, `url`/`name` обрезаются; повтор ингредиента без учёта регистра, пустое имя и
  пустое количество отбрасываются; текст `recipes.ingredients` собирается через « — ».
- [x] `test_record_from_row_rejects_unusable_rows` — нет `url`/`name`, `url` не http(s), длина
  url больше `varchar(255)` или названия больше `varchar(200)` → строка пропускается.
- [x] `test_parse_ingredients_accepts_the_dataset_shapes` — словарь, JSON-строка, Python-литерал
  из CSV (`{'Яйцо куриное': '5 шт', 'Соль': None}`), строки «имя: количество», список словарей и
  строк; `""`/`nan`/`None` дают пустой список, пустой список рендерится как «ингредиенты не указаны».
- [x] `test_iter_rows_reads_json_csv_and_jsonl` — три формата дают те же строки; CSV без колонок
  датасета и неизвестное расширение — понятная ошибка `DatasetError`, а не пустой импорт; CSV в
  формате pandas (литерал + пустая ячейка) разбирается в ингредиенты и в текст-заглушку.
- [x] `test_import_dataset_dry_run_does_not_need_a_database` — `db=None` + `dry_run=True`: 12
  рецептов и 60 ингредиентов разобраны, вставок 0; `--limit` ограничивает разбор; строка без url
  считается пропущенной.
- [x] `test_download_dataset_unpacks_the_archive_and_sends_the_credentials` — Basic-заголовок из
  `KAGGLE_USERNAME`/`KAGGLE_KEY`, таймаут передаётся в `opener`, zip распакован, сам архив удалён.
- [x] `test_download_dataset_requires_the_kaggle_credentials` — без переменных окружения —
  `DatasetError` (доступ к Kaggle только через env).
- [x] `test_cli_dry_run_and_error_codes` — нет файла → код 1; нет `DATABASE_URL` без `--dry-run` →
  код 2; `--dry-run` без базы → 0; путь из `POVARENOK_DATASET` и `--limit`.
- [x] `test_import_fills_recipes_and_recipe_ingredients` — 12 рецептов и 60 строк ингредиентов,
  `instruction`/`difficulty_level` = `NULL`, `source_url` заполнен, порядок `sort_order`, `NULL`
  в количестве, литерал и список разобраны.
- [x] `test_repeated_import_is_idempotent_and_honours_the_limit` — импорт с `limit=3`, затем полный
  (9 новых + 3 дубля), затем повторный (0 вставок, 12 дублей); количество строк не меняется.
- [x] `test_cli_imports_the_sample` — CLI с `DATABASE_URL` импортирует сэмпл, повторный запуск
  ничего не добавляет.
- [x] `test_module_entry_point_runs_the_cli` — `python -m app.importer --help` печатает
  использование и завершается с кодом 0: документированная точка входа работает, а не только
  `app.importer.cli`.

### `tests/test_openapi_contract.py` — 22 кейса (17 без БД)

Проверяет не поведение отдельного адреса, а сам контракт: файл, его соответствие коду и тела
ответов. Единственный файл набора, который открывает `openapi.yaml`.

- [x] `test_the_contract_is_a_valid_openapi_document` — `openapi-spec-validator` принимает файл;
  версия 3.0.x, `info.title`/`info.version` на месте, `servers` объявлен **в корне** документа
  (вложенный в `info` делал контракт невалидным, а Swagger UI — без адреса), у каждой переменной
  в `url` есть описание в `variables`.
- [x] `test_every_operation_documents_a_success_answer` — у каждой операции есть 2xx-ответ.
- [x] `test_every_token_protected_operation_documents_401` — где объявлен `security: bearerAuth`,
  там описан и 401 (проверка не вырождается: кейс падает, если защищённых операций не осталось).
- [x] `test_the_contract_describes_exactly_the_routes_of_the_application` — адреса и методы из
  файла совпадают с `app.url_map` в обе стороны (`/health` и `/ready` описаны в контракте, служебный
  `/static` исключён): недокументированный маршрут и «документированный, но забытый» падают отдельно.
- [x] `test_the_pagination_limits_match_the_application_constants` — у `GET /recipes`,
  `GET /favorite_recipes`, `GET /fridge_items` схема `limit`/`offset` равна константам
  `app/validation.py` (1..200, по умолчанию 50; 0..1 000 000, по умолчанию 0).
- [x] `test_failure_answers_match_the_error_schema` (11 параметров) — 401 без токена на `/protected`,
  `/favorite_recipes`, `/notify_expired` и трёх адресах таймеров; 400 на `?limit=0`, `?offset=abc`,
  неполный `/register`, пустой `/login`, не-объект в `POST /recipes`; тело каждого — ровно
  `{"error": "..."}`.
- [x] `test_the_system_answers_match_the_contract` — `GET /` (text/plain), `GET /health` (200),
  `GET /ready` (503 без базы) по схемам контракта.
- [x] `test_authentication_and_recipe_answers_match_the_contract` — регистрация, вход, `/protected`
  и весь CRUD рецепта, включая документированный 404 после удаления.
- [x] `test_favorites_fridge_and_notification_answers_match_the_contract` — избранное (добавление,
  страница, удаление), холодильник (список и добавление), `/notify_expired`, `/suggest_recipes`,
  `/recommend_recipes`, `/user_preferences`, `/delete_expired`, `/delete_expired_products`.
- [x] `test_an_imported_recipe_matches_the_contract` — рецепт из импортёра: три `nullable`-поля
  равны `null`, `ingredient_list` идёт по `sort_order`, `quantity` может быть `null` — и в карточке,
  и в странице списка.
- [x] `test_timer_answers_match_the_contract` — таймеры (спринт 3, задача 1): `POST /timers`
  (201, `ends_at` — `date-time` с offset и позже `started_at`), `GET /timers/active`,
  `DELETE /timers/{id}` и документированный повторный 404; плюс 400 «у рецепта нет времени» и 404
  на неизвестный рецепт.
- [x] `test_a_parsed_recipe_matches_the_contract` — разобранный рецепт (спринт 3, задача 2):
  `steps`, `servings` и `nutrition` соответствуют `Recipe`/`RecipeStep`/`RecipeNutrition` и в
  карточке, и в странице списка; `nutrition` объявлен `nullable`, поэтому `null` тоже валиден.

## Примечания для отчётности

- **Осознанные отклонения от CONTRIBUTION.md, зафиксированные тестами** (поведение задано
  `openapi.yaml`, поэтому менять его нужно вместе с контрактом): `POST /recipes` и
  `POST /user_preferences` не требуют токена, `GET /fridge_items` и
  `DELETE /delete_expired_products` работают со всеми пользователями.
- **Изоляция данных**: `test_delete_expired_touches_only_the_user_from_the_token` — кейс,
  доказывающий, что защищённый адрес берёт `user_id` из токена, а не из тела запроса.
- **Одно правило для просроченных продуктов**: граница задана в `app/models/fridge.py`
  (`EXPIRED_CONDITION = "expiration_date < CURRENT_DATE"`) и используется `GET /notify_expired`,
  `DELETE /delete_expired`, `DELETE /delete_expired_products`, `GET /suggest_recipes` и воркером.
  Дата берётся из базы, а не из Python: иначе web-процесс и PostgreSQL в разных часовых поясах
  давали бы разный ответ около полуночи. Кейсы — `test_notify_expired_and_delete_expired_products_use_one_rule`
  и `test_delete_expired_products_uses_the_database_date_as_the_boundary`.
- **Фикстуры** (`tests/conftest.py`): `app`/`client` — приложение без БД; `db_app`/`db_client`/`db`
  — приложение с БД, фасад базы для SQL-проверок и очистка всех двенадцати таблиц перед каждым
  кейсом (`TRUNCATE ... RESTART IDENTITY CASCADE`); `register_user` и `add_fridge_items` —
  подготовка данных через настоящие HTTP-запросы; `add_relative_fridge_items` — продукты с датами
  относительно часов базы (`CURRENT_DATE + смещение`), чтобы проверять границу по тому же правилу;
  `db_app_factory(**env)` собирает приложения с дополнительными переменными окружения — так
  тестируются флаг `SMART_RECOMMENDATIONS_ENABLED` (второе приложение на той же базе) и лимит
  запросов (`RATE_LIMIT_ENABLED` и `RATE_LIMIT_MAX_REQUESTS`).
- **Импорт датасета проверяется без сети и без сырых данных**: синтетический сэмпл
  `tests/data/povarenok_sample.json` (12 рецептов, 60 строк ингредиентов) повторяет структуру
  Kaggle-датасета, включая Python-литерал из CSV и `None` вместо количества; скачивание
  проверяется подставным `opener`, поэтому `pytest` не зависит от Kaggle и `KAGGLE_KEY`.
- **Почему кейсов немного**: набор намеренно сделан обозримым для новичка — один успешный кейс
  на адрес и один «плохой». Множество проверок внутри одного кейса (например, 10 некорректных
  тел в `test_add_fridge_items_validates_the_payload`) оформлено обычным циклом `for`, поэтому
  тестовых функций мало, а падение всё равно указывает на конкретное тело через `assert ..., payload`.
- **Контракт проверяется сам, а не пересказывается**: `tests/test_openapi_contract.py` читает
  `openapi.yaml` и (1) валидирует файл по спецификации OpenAPI 3.0, (2) сравнивает его адреса и
  методы с `app.url_map`, а лимиты `limit/offset` — с константами `app/validation.py`,
  (3) проверяет тела реальных ответов по схемам файла (`openapi-schema-validator` понимает
  `nullable`). Ручной список маршрутов, который раньше жил в `tests/test_system.py`, удалён.
- **Результат последнего прогона** (12.11.2026, ветка `feat/recipe-pages`): без БД —
  `80 passed, 71 skipped` (exit 0), с PostgreSQL 15 в контейнере — `151 passed, 0 skipped`
  (exit 0), `ruff`/`black` — без замечаний; покрытие того же прогона — 88,7 % строк и 82,5 %
  ветвей (`docs/test-coverage.md`). Те же 151 кейс повторяет CI-workflow `Backend CI`
  на PostgreSQL 15.
- **Таймеры проверяются там, где это имеет смысл**: сервер отвечает за дедлайн (`ends_at`),
  изоляцию по токену и состояния, поэтому тесты сравнивают `ends_at − started_at` и содержимое
  таблицы. Точность отрисовки — свойство клиентского алгоритма (`docs/timer.md` §5): 250-мс шаг
  перерисовки и остаток, посчитанный от пары «`ends_at` − `server_time`», поэтому отсчёт не
  дрейфует; pytest-ом это не проверяется и не должно.
