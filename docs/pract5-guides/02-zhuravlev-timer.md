# Журавлев Владислав, вариант 6

**Ветка:** `refactor/pract5-timer`

**Файлы:** `backend/app/services/timer_service.py`, `backend/app/api/timers.py`.

## Что делаем

Сейчас `active_timers()` делает два дела сразу: сначала закрывает просроченные таймеры, потом
читает активные. Разделяем на две функции:

- `close_expired_timers(db, user_id)` — только меняет данные;
- `active_timers(db, user_id)` — только читает.

В API-обработчике сначала вызываем закрытие, потом чтение. Ответ пользователю не меняется.

## Как делать

1. В `timer_service.py` добавь `close_expired_timers()`. Она просто вызывает
   `timers_model.close_expired()` и возвращает результат.
2. Убери `timers_model.close_expired()` из `active_timers()`. Поправь docstring: теперь функция
   только читает.
3. В `api/timers.py` в обработчике `GET /timers/active` сделай два вызова:

   ```python
   timer_service.close_expired_timers(db, user_id)
   return jsonify(timer_service.active_timers(db, user_id)), 200
   ```

4. Проверь:

   ```bash
   cd backend
   ruff check .
   black --check .
   pytest tests/test_timers.py -q
   pytest
   ```

## Что писать в PR

Заголовок:

```text
refactor(timers): separate query from modifier
```

В описании объясни, что поведение то же: сначала закрываются просроченные, потом отдаётся список.
Плюс в том, что `active_timers()` теперь безопасно вызывать где угодно — она не пишет в базу.

## Что может спросить ревьюер

- «Почему не наоборот: сначала прочитать, потом закрыть?» — тогда в ответ могут попасть уже
  просроченные таймеры.
- «Не нужна ли транзакция?» — оба вызова и так работают в рамках текущего соединения, как и
  раньше; поведение не меняем.
- «Где тест на разделение?» — можно добавить тест на `close_expired_timers`, но не переписывай
  существующие тесты без необходимости.

## Осторожно

Не меняй SQL в `models/timers.py`, названия полей JSON и другие функции. Только эти два файла.
