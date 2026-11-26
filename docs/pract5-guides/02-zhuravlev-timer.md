# Журавлев Владислав, вариант 6: пошаговая инструкция

**Ветка:** `refactor/pract5-timer`

**Файлы:** `backend/app/services/timer_service.py`, `backend/app/api/timers.py`.

**Что должно получиться:** `active_timers()` больше не меняет данные. Появляется отдельная
функция `close_expired_timers()`, а API-обработчик вызывает её перед чтением.

## Шаг 1. Подготовить ветку

```bash
git switch main
git pull
git switch -c refactor/pract5-timer
git status
```

## Шаг 2. Добавить `close_expired_timers`

Файл: `backend/app/services/timer_service.py`.

Перед функцией `active_timers` (около строки 68) вставить:

```python
def close_expired_timers(db: Database, user_id: int) -> int:
    """Close the timers whose deadline has already passed."""
    return timers_model.close_expired(db, user_id)
```

Импорты менять не нужно: `Database` и `timers_model` уже импортированы.

## Шаг 3. Убрать изменение данных из `active_timers`

Было:

```python
def active_timers(db: Database, user_id: int) -> dict:
    """Return ``ActiveTimersResponse``: the running timers of the token owner.

    Expired timers are closed here instead of by a background worker: a single UPDATE
    keeps the table honest, is idempotent and costs nothing while no timer runs
    (``docs/timer.md``, "почему нет воркера").
    """
    timers_model.close_expired(db, user_id)
    rows = timers_model.list_active(db, user_id, limit=MAX_ACTIVE_TIMERS)
```

Стало:

```python
def active_timers(db: Database, user_id: int) -> dict:
    """Return the running timers of the user (read-only)."""
    rows = timers_model.list_active(db, user_id, limit=MAX_ACTIVE_TIMERS)
```

Остальную часть функции не менять: `server_time` и `serialize_timer` остаются как были.

## Шаг 4. Обновить обработчик API

Файл: `backend/app/api/timers.py`, обработчик `GET /timers/active`.

Было:

```python
@bp.get("/timers/active")
@token_required
def active_timers() -> tuple:
    """Return the running timers of the token owner together with ``server_time``."""
    return jsonify(timer_service.active_timers(get_db(), current_user_id())), 200
```

Стало:

```python
@bp.get("/timers/active")
@token_required
def active_timers() -> tuple:
    """Return the running timers of the token owner together with ``server_time``."""
    db = get_db()
    user_id = current_user_id()
    timer_service.close_expired_timers(db, user_id)
    return jsonify(timer_service.active_timers(db, user_id)), 200
```

Порядок важен: сначала закрываются просроченные, потом читается список. Иначе в ответ могут
попасть уже истёкшие таймеры.

## Шаг 5. Проверить

```bash
cd backend
ruff check .
black --check .
pytest tests/test_timers.py -q
pytest
```

Если тест падает, проверить, что `close_expired_timers` вызывается до `active_timers` и что
ответ API не изменился.

## Шаг 6. Коммит и push

```bash
git diff --stat
git diff --check
git add backend/app/services/timer_service.py backend/app/api/timers.py
git commit -m "refactor(timers): separate query from modifier"
git push -u origin refactor/pract5-timer
```

В коммите только два файла. SQL, модели и JSON не меняются.

## Шаг 7. PR

Заголовок:

```text
refactor(timers): separate query from modifier
```

В описании указать:

- было: одна функция закрывала просроченные и читала активные;
- стало: `close_expired_timers()` и `active_timers()` отдельно;
- API-ответ не изменился;
- проверки и `git diff --stat`.

Ревьюер: Потапов Артем.

## Частые ошибки

- `close_expired_timers` вызван после чтения — в ответе остаются просроченные;
- в `active_timers` остался старый вызов `timers_model.close_expired`;
- изменился докстринг, но не код, или наоборот;
- в PR попали `models/timers.py` или тесты без необходимости.
