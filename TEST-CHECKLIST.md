# Чек-лист тестов API

Приложение к отчёту `TASKS-REPORT.md`: полный перечень автоматических проверок backend
(`backend/tests/`, `pytest`) и того, что именно проверяет каждый кейс.

**Состав набора:** **41 кейс в 9 файлах**. 13 кейсов работают без базы (проверка входных
данных, работа с токеном, служебные адреса, компоненты ML-заглушки), 28 — против реальной
PostgreSQL (включая саму схему БД). На каждый адрес из `openapi.yaml` приходится 1–2 кейса;
адресов по-прежнему 19: модуль рекомендаций включается флагом `SMART_RECOMMENDATIONS_ENABLED`
внутри `GET /recommend_recipes` (`tests/test_smart_recommendations.py`), новых маршрутов нет.

## Как запускать

```bash
cd backend
python -m pytest                 # без БД: 13 passed, 28 skipped (DB-кейсы скипаются)
TEST_DATABASE_URL=postgresql://postgres:changeme@localhost:5432/mydatabase python -m pytest
                                 # с БД: 41 passed
```

То же самое автоматически выполняет CI: workflow `Backend CI`
(`.github/workflows/backend-tests.yml`) поднимает PostgreSQL 15 и запускает `python -m pytest`
на каждый push в `main` и на каждый pull request.

## Итог последнего прогона

| Файл | Кейсов | Без БД | С БД | Тема |
|---|---|---|---|---|
| `tests/test_system.py` | 6 | 5 | 1 | служебные адреса, список маршрутов, формат ошибок |
| `tests/test_auth.py` | 6 | 4 | 2 | регистрация, вход, проверка токена |
| `tests/test_recipes.py` | 6 | 0 | 6 | CRUD рецептов |
| `tests/test_fridge.py` | 3 | 0 | 3 | холодильник и удаление просроченного |
| `tests/test_user_preferences.py` | 2 | 1 | 1 | аллергии и предпочтения |
| `tests/test_notifications_recommendations.py` | 5 | 1 | 4 | уведомления и рекомендации |
| `tests/test_database.py` | 8 | 0 | 8 | схема БД, ограничения, триггеры, таблицы без адресов |
| `tests/test_ml_engine.py` | 2 | 2 | 0 | компоненты ML-модуля: предобработка, KNN, бонус холодильника |
| `tests/test_smart_recommendations.py` | 3 | 0 | 3 | `GET /recommend_recipes` с флагом и без него |
| **Всего** | **41** | **13** | **28** | |

Проверено 16.10.2026 на ветке `feat/smart-recommendations`: без БД — `13 passed, 28 skipped`
(exit 0); с реальной PostgreSQL 15 (контейнер Docker) — `41 passed, 0 skipped` (exit 0);
`ruff check .` и `black --check .` — без замечаний. Те же 41 кейс повторяет CI на PostgreSQL 15:
там доступность базы контролируется отдельным шагом, поэтому набор не может «позеленеть» на
одних пропусках.

## Покрытие эндпоинтов: 19 адресов, 1–2 кейса на адрес

| Адрес | Кейсы | Что проверяется |
|---|---|---|
| `GET /` | `test_index_returns_the_greeting` | 200 и текст приветствия из контракта |
| `GET /health` | `test_health_is_ok_without_a_database` | 200 `{"status":"ok"}` без обращения к БД |
| `GET /ready` | `test_ready_reports_a_missing_database`, `test_ready_reports_a_healthy_database` | 503 «база недоступна» и 200 «база ok» |
| `POST /register` | `test_register_creates_a_user`, `test_register_rejects_invalid_payloads` | 201 + пароль scrypt-хэшем + нормализация аллергий + отказ на дубликаты; 400 на 9 «плохих» тел и не-JSON |
| `POST /login` | `test_login_returns_a_token`, `test_login_requires_email_and_password` | 401 на неверный пароль и неизвестный email, 200 + `token`; 400 без email/password |
| `GET /protected` | `test_protected_accepts_a_valid_token`, `test_protected_rejects_bad_tokens` | 200 с `user_id` из токена; 401 в 6 вариантах (нет заголовка, чужая схема, пустой/битый/просроченный токен, без `sub`) |
| `POST /user_preferences` | `test_preferences_are_stored_normalized_and_cleared`, `test_user_preferences_validation` | 200 + запись в `users` и `user_allergy_preferences` (замена без дублей, очистка), 400 на неизвестный `user_id`; 400 на 6 некорректных тел |
| `GET /recipes` | `test_list_recipes_returns_every_recipe` | 200, список рецептов, отсутствие удалённого `cuisine_type` |
| `POST /recipes` | `test_create_recipe_stores_it_under_the_database_column_names`, `test_create_recipe_validates_the_payload` | 201 + запись в колонки `recipe_name`/`instruction`; 400 на 8 некорректных тел |
| `GET /recipes/{id}` | `test_get_recipe_by_id` | 200 с телом рецепта, 404 на неизвестный id |
| `PUT /recipes/{id}` | `test_update_recipe` | 200, изменение сохранено; 400 на неполное тело, 404 на неизвестный id |
| `DELETE /recipes/{id}` | `test_delete_recipe` | 200, рецепт исчез из списка; 404 на неизвестный id |
| `GET /fridge_items` | `test_add_and_list_fridge_items` | 200, поля продукта, `id` = `fridge_items.item_id` |
| `POST /fridge_items` | `test_add_and_list_fridge_items`, `test_add_fridge_items_validates_the_payload` | 201 + сохранение батча; 400 на 10 некорректных тел (включая `quantity = 0` и неизвестного пользователя) |
| `DELETE /delete_expired_products` | `test_delete_expired_products_removes_only_expired_items` | удаляются только просроченные, повторный вызов безопасен |
| `GET /notify_expired` | `test_notify_expired_lists_only_expired_products` | пустой холодильник и список просроченных продуктов |
| `DELETE /delete_expired` | `test_delete_expired_touches_only_the_user_from_the_token` | удаляются продукты только того пользователя, чей токен |
| `GET /suggest_recipes` | `test_suggest_recipes_uses_the_expired_products` | подсказки по просроченным продуктам + запись в `generated_recipes` |
| `GET /recommend_recipes` | `test_recommend_recipes_uses_the_fridge_and_skips_the_allergies` | рекомендации по холодильнику без аллергенов, история выдачи, пустой холодильник, аллергии из текстовой колонки |

## Что проверяет каждый файл

### `tests/test_system.py` — 6 кейсов (5 без БД)

- [x] `test_index_returns_the_greeting` — `GET /` → 200, `text/plain`, точный текст приветствия.
- [x] `test_health_is_ok_without_a_database` — liveness-проба работает без базы (200).
- [x] `test_ready_reports_a_missing_database` — readiness-проба без базы → 503 `{"database":"unavailable"}`.
- [x] `test_ready_reports_a_healthy_database` — с базой → 200 `{"database":"ok"}`.
- [x] `test_registered_routes_match_the_contract` — в приложении зарегистрированы ровно 19 адресов
  и их HTTP-методы из `openapi.yaml` (плюс `/health` и `/ready`); лишних и забытых маршрутов нет.
- [x] `test_unknown_address_and_method_return_an_error_object` — 404 и 405 отдают единый
  формат ошибки `{"error": "..."}`.

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

### `tests/test_recipes.py` — 6 кейсов (все с БД)

- [x] `test_create_recipe_stores_it_under_the_database_column_names` — 201 и запись в колонки
  `recipe_name`, `ingredients`, `instruction`, `difficulty_level` (API-поля `name`/`instructions`
  переводятся сериализатором).
- [x] `test_create_recipe_validates_the_payload` — 400 на 8 тел: нет одного из четырёх
  обязательных полей, не строка, значения длиннее колонок (`200`/`100`/`50` символов).
- [x] `test_list_recipes_returns_every_recipe` — 200, оба созданных рецепта в списке,
  `id` — целое, `cuisine_type` больше не отдаётся.
- [x] `test_get_recipe_by_id` — 200 с полным телом рецепта; неизвестный id → 404.
- [x] `test_update_recipe` — 200, изменённые поля сохранены (остальные не потеряны);
  неполное тело → 400, неизвестный id → 404.
- [x] `test_delete_recipe` — 200, рецепт исчез, список пуст; повторное удаление → 404.

### `tests/test_fridge.py` — 3 кейса (все с БД)

- [x] `test_add_and_list_fridge_items` — 201 и сообщение `N fridge item(s) added`; в списке
  корректные поля, `id` ответа совпадает с `fridge_items.item_id`, `quantity` — целое.
- [x] `test_add_fridge_items_validates_the_payload` — 400 в цикле на 10 тел: тело не массив,
  пустой массив, элемент не объект, пустой объект, нет `quantity`, `quantity = 0` (CHECK в схеме),
  дробное `quantity`, длинное имя продукта, дата не в ISO 8601, несуществующий `user_id`.
- [x] `test_delete_expired_products_removes_only_expired_items` — удаляется только просроченный
  продукт, продукт со сроком «сегодня» остаётся; повторный вызов удаляет 0 и не падает.

### `tests/test_user_preferences.py` — 2 кейса (1 без БД)

- [x] `test_preferences_are_stored_normalized_and_cleared` — 200; значения попадают в
  `users.allergies`/`preferences` текстом и в `user_allergy_preferences` строками; повторный
  вызов заменяет старые значения без дублей; пустой список очищает и то, и другое;
  неизвестный `user_id` → 400.
- [x] `test_user_preferences_validation` — 400 в цикле на 6 тел (нет `user_id`, `user_id`
  строкой или нулём, аллергии не списком, элементы не строки, пустые элементы).

### `tests/test_notifications_recommendations.py` — 5 кейсов (1 без БД)

- [x] `test_all_four_routes_require_a_token` — 401 для `/notify_expired`, `/delete_expired`,
  `/suggest_recipes`, `/recommend_recipes` без токена и с испорченным токеном.
- [x] `test_notify_expired_lists_only_expired_products` — пустой холодильник → сообщение
  `No expired products found`; с продуктами → в `expired_products` только просроченный.
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

### `tests/test_database.py` — 8 кейсов (все с БД)

Файл — «исполняемая» копия схемы `docs/db_scheme.png` и проверка того, что не покрыто адресами.

- [x] `test_tables_columns_and_primary_keys_match_the_diagram` — ровно 8 таблиц, у каждой
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
  снятие, удаление рецепта убирает его из избранного (у эндпоинта пока нет адреса в контракте,
  поэтому проверяется через `app.models`).
- [x] `test_generated_recipes_keep_what_was_offered` — `generated_recipes`: запись выдачи,
  пустая выдача ничего не пишет, несуществующий рецепт отклоняется, очистка истории,
  каскад при удалении рецепта.

## Примечания для отчётности

- **Осознанные отклонения от CONTRIBUTION.md, зафиксированные тестами** (поведение задано
  `openapi.yaml`, поэтому менять его нужно вместе с контрактом): `POST /recipes` и
  `POST /user_preferences` не требуют токена, `GET /fridge_items` и
  `DELETE /delete_expired_products` работают со всеми пользователями.
- **Изоляция данных**: `test_delete_expired_touches_only_the_user_from_the_token` — кейс,
  доказывающий, что защищённый адрес берёт `user_id` из токена, а не из тела запроса.
- **Фикстуры** (`tests/conftest.py`): `app`/`client` — приложение без БД; `db_app`/`db_client`/`db`
  — приложение с БД, фасад базы для SQL-проверок и очистка всех восьми таблиц перед каждым
  кейсом (`TRUNCATE ... RESTART IDENTITY CASCADE`); `register_user` и `add_fridge_items` —
  подготовка данных через настоящие HTTP-запросы; `db_app_factory(**env)` собирает приложения с
  дополнительными переменными окружения — так тестируется флаг `SMART_RECOMMENDATIONS_ENABLED`
  (второе приложение на той же базе).
- **Почему кейсов немного**: набор намеренно сделан обозримым для новичка — один успешный кейс
  на адрес и один «плохой». Множество проверок внутри одного кейса (например, 10 некорректных
  тел в `test_add_fridge_items_validates_the_payload`) оформлено обычным циклом `for`, поэтому
  тестовых функций мало, а падение всё равно указывает на конкретное тело через `assert ..., payload`.
- **Результат последнего прогона** (16.10.2026, ветка `feat/smart-recommendations`): без БД —
  `13 passed, 28 skipped` (exit 0), с PostgreSQL 15 в контейнере — `41 passed, 0 skipped`
  (exit 0), `ruff`/`black` — без замечаний. Те же 41 кейс повторяет CI-workflow `Backend CI`
  на PostgreSQL 15.
