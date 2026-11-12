# Таймеры в рецепте

Документ описывает, как в сервисе устроен таймер приготовления, почему он не «врёт» и где
заканчиваются возможности браузера. Постановка — user story 7 в
[`docs/user_story.md`](user_story.md), работа — задача 1 спринта 3
([`docs/sprint-3-plan.md`](sprint-3-plan.md)).

## 1. Что делает пользователь

1. Открывает рецепт. Если у рецепта объявлено время (`cooking_time_minutes`), карточка
   показывает «≈ 25 мин» и кнопку «Поставить таймер»; импортированные рецепты времени не имеют —
   для них длительность вводится вручную.
2. Нажимает «Старт». Клиент шлёт `POST /timers`, получает `timer.ends_at` и `server_time` и
   рисует обратный отсчёт.
3. Когда время вышло, вкладка звенит, вибрирует (телефон), показывает уведомление и меняет
   заголовок. Таймер исчезает из списка активных, в базе он `finished`.
4. Перезагрузка страницы или второе устройство не сбрасывают отсчёт: список активных таймеров
   приходит с сервера вместе с его текущим временем.

## 2. Главное решение: сервер хранит дедлайн, а не счётчик

Типичная ошибка — считать секунды в браузере (`setInterval(() => seconds--, 1000)`). Тогда
ошибка копится на каждом тике, а фоновая вкладка вообще «засыпает»: Chrome душит таймеры до
одного раза в минуту, Safari на телефоне останавливает страницу при блокировке экрана.

Поэтому:

- база хранит **абсолютный момент** `timers.ends_at = started_at + duration_seconds`;
- ответ API всегда содержит **пару** `ends_at` + `server_time`;
- клиент один раз переводит эту пару в монотонную шкалу страницы (`performance.now()`) и дальше
  каждую отрисовку считает `остаток = (ends_at − server_time) − (сейчас − момент_якоря)`.

Из формулы исчезли и часы устройства (они могут врать на минуты), и накопление ошибки тиков:

| Источник ошибки | Что было бы с наивным таймером | Как решено |
|---|---|---|
| Счёт тиков | +2–10 с за 30 минут | тики только перерисовывают разность, а не уменьшают счётчик |
| Часы устройства (`Date.now()`) | ошибка на минуты, смена пояса, NTP-скачок | клиент не использует свои часы: обе величины приходят с сервера |
| Фоновая вкладка (throttling) | отсчёт «замирает» на минуты | при возврате на вкладку остаток пересчитывается от дедлайна |
| Сон/блокировка устройства | монотонные часы и таймеры стоят | после долгого отсутствия — `GET /timers/active` и новый якорь |
| Несколько web-процессов (gunicorn) | состояние таймера живёт в памяти одного воркера | состояние в PostgreSQL; `now()` — часы базы |

## 3. Данные

```sql
CREATE TABLE timers (
    id               serial      PRIMARY KEY,
    user_id          integer     NOT NULL REFERENCES users (id)   ON DELETE CASCADE,
    recipe_id        integer     NOT NULL REFERENCES recipes (id) ON DELETE CASCADE,
    label            varchar(100) NOT NULL,          -- по умолчанию название рецепта
    duration_seconds integer     NOT NULL CHECK (duration_seconds BETWEEN 1 AND 86400),
    started_at       timestamptz NOT NULL DEFAULT now(),
    ends_at          timestamptz NOT NULL,
    status           varchar(16) NOT NULL DEFAULT 'running'
                     CHECK (status IN ('running', 'finished', 'cancelled')),
    closed_at        timestamptz,
    created_at       timestamp   NOT NULL DEFAULT current_timestamp,
    CONSTRAINT timers_ends_after_start_check CHECK (ends_at > started_at)
);
```

Три отличия от остальной схемы, каждое осознанное:

- `timestamptz` вместо `timestamp`: наивное время в таймере ломается при смене пояса и переходе
  на летнее время;
- `duration_seconds`, а не минуты: шаг «варить 90 секунд» — реальный случай, а рецепт при этом
  объявляет время в минутах (`recipes.cooking_time_minutes`);
- `closed_at = ends_at` у истёкшего таймера: в колонке фиксируется, **когда** таймер должен был
  закончиться, а не когда его заметили.

## 4. API

| Адрес | Назначение |
|---|---|
| `POST /timers` | запуск: `{recipe_id, duration_seconds?, label?}` → 201 `{server_time, timer}` |
| `GET /timers/active` | идущие таймеры пользователя + `server_time` (для восстановления после перезагрузки) |
| `DELETE /timers/{id}` | отмена; чужой/неизвестный/уже закончившийся → 404 |

`duration_seconds` необязателен: если его нет, сервер берёт `recipes.cooking_time_minutes × 60`.
Для импортированного рецепта (времени нет) это 400 с текстом «Recipe N has no cooking time, send
duration_seconds» — лучше явная ошибка, чем таймер неизвестной длины.

```bash
# старт на время рецепта
curl -s -X POST http://localhost:8000/timers \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"recipe_id": 12}'
# {"server_time":"2026-11-12T10:00:00.123+00:00",
#  "timer":{"id":3,"recipe_id":12,"label":"Гречка","duration_seconds":900,
#           "started_at":"2026-11-12T10:00:00.123+00:00",
#           "ends_at":"2026-11-12T10:15:00.123+00:00",
#           "remaining_seconds":900,"status":"running"}}

curl -s http://localhost:8000/timers/active -H "Authorization: Bearer $TOKEN"
curl -s -X DELETE http://localhost:8000/timers/3 -H "Authorization: Bearer $TOKEN"

## 5. Алгоритм клиента

Ниже — эталонная реализация, по которой проверялась логика. Она не зависит от фреймворка:
достаточно, чтобы страница умела `fetch` и `performance.now()`.

```js
// 1. Старт: сервер — единственный источник времени.
async function startTimer(recipeId, durationSeconds = null, label = null) {
  const res = await fetch('/timers', {
    method: 'POST',
    headers: {'Content-Type': 'application/json', Authorization: `Bearer ${token}`},
    body: JSON.stringify({recipe_id: recipeId, duration_seconds: durationSeconds, label}),
  });
  if (!res.ok) throw new Error((await res.json()).error);
  return anchor(await res.json());
}

// 2. Якорь: остаток на момент ответа = ends_at − server_time (оба значения с сервера),
//    дальше его отсчитывают монотонные часы страницы. Часы устройства не участвуют.
function anchor({server_time, timer}) {
  return {
    id: timer.id,
    label: timer.label,
    remaining0: Date.parse(timer.ends_at) - Date.parse(server_time),
    anchorAt: performance.now(),
    rung: false,
  };
}

const remainingMs = (t) => t.remaining0 - (performance.now() - t.anchorAt);

// 3. Перерисовка: всегда «дедлайн минус сейчас», поэтому ошибка не копится.
function render(t) {
  const ms = remainingMs(t);
  document.querySelector(`[data-timer="${t.id}"]`).textContent =
    formatClock(Math.max(0, Math.ceil(ms / 1000)));        // MM:SS
  if (ms <= 0 && !t.rung) { t.rung = true; ring(t); }      // сработать ровно один раз
}
setInterval(() => timers.forEach(render), 250);

// 4. Возврат на вкладку: браузер душил тики — пересчитываем.
//    Если вкладка была скрыта дольше минуты (сон, карман, блокировка) — сверяемся с сервером.
document.addEventListener('visibilitychange', async () => {
  if (document.hidden) return;
  if (Date.now() - lastSyncAt > 60_000) await resync();    // GET /timers/active → новые якоря
  timers.forEach(render);
  keepScreenOn();
});
window.addEventListener('pageshow', resync);               // возврат из bfcache

// 5. Звонок. AudioContext разблокирован на клике «Старт», иначе автоплей запрещён
//    и пикнуть в нужный момент будет нечем.
async function ring(t) {
  await beep(ctx, [880, 0, 880, 0, 880]);                  // осциллятор, без звуковых файлов
  navigator.vibrate?.([200, 100, 200, 100, 200]);
  if (Notification.permission === 'granted') new Notification('Таймер', {body: t.label});
  document.title = '⏰ ' + t.label;
}

// 6. Экран не гаснет, пока готовим (Chrome/Edge, Safari 16.4+).
async function keepScreenOn() {
  try { await navigator.wakeLock?.request('screen'); } catch { /* браузер не умеет */ }
}
```

Чего делать **нельзя**: считать оставшиеся секунды вычитанием единицы на каждом тике; брать
текущее время из `Date.now()` и сравнивать с `ends_at` (часы телефона могут отличаться на минуты);
перезапускать отсчёт с нуля после `visibilitychange`.

## 6. Насколько это точно

| Ситуация | Показания на экране | Звонок |
|---|---|---|
| вкладка открыта, экран включён (Wake Lock) | ±0,25 с (шаг отрисовки), без накопления | ±0,25 с |
| вкладка в фоне (Chrome, > 5 мин) | верны в момент, когда браузер даст тик | до 60 с позже |
| телефон заблокирован / браузер свёрнут | верны после возврата (пересчёт от дедлайна) | нет |
| перезагрузка страницы, второе устройство | верны (дедлайн и `server_time` с сервера) | да, если страница открыта |
| вкладка закрыта | — | нет (нужен Web Push, см. §8) |

Граница возможного честная: веб-страница не исполняет код, когда её нет, поэтому «звенеть при
закрытой вкладке» можно только push-уведомлением через service worker. Это отдельная задача, а не
недоработка таймера.

## 7. Почему нет воркера и паузы

- **Воркер не нужен**: `GET /timers/active` перед чтением выполняет один `UPDATE`, который
  закрывает просроченные таймеры (`status = finished`, `closed_at = ends_at`). Это идемпотентно и
  стоит ноль, пока таймеров нет. Воркер понадобится только для push-уведомлений и истории.
- **Паузы нет**: в кулинарном таймере пауза почти всегда означает «перезапустить»; каждое
  состояние (`paused`, `remaining_on_pause`, пересчёт `ends_at`) добавляет ветки в API, тесты и
  документацию, не улучшая точность. Если понадобится — отдельная задача с явным критерием.

## 8. Что осталось за рамками

- **Web Push** — звонок при закрытой вкладке (нужны service worker, HTTPS, ключи VAPID).
- **Таймеры по шагам** — в `recipes.instruction` нет структурированных шагов, поэтому шаг не
  отличить от строки текста; сначала нужны шаги как данные (user story 6).
- **История и статистика** — какие таймеры запускали и доводили до конца (таблица уже это хранит:
  `finished`/`cancelled`).
- **Синхронный отсчёт на нескольких устройствах в реальном времени** — требует SSE/WebSocket;
  на точность не влияет, потому что рисует всё равно локальный клиент.

## 9. Как проверить

```bash
cd backend
pytest tests/test_timers.py -q                       # 11 кейсов
TEST_DATABASE_URL=... pytest tests/test_openapi_contract.py -q
```

Кейсы проверяют то, что можно проверить на сервере: дедлайн равен `started_at + duration`, время
берётся из базы, чужой таймер не виден, истёкший закрывается чтением, лимит активных, 400/401/404.
Точность отрисовки — свойство алгоритма из §5 и ограничений из §6, её нельзя «протестировать»
pytest-ом.

```
