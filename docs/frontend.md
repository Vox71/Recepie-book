# Фронтенд: React, TypeScript и роутинг

Документ описывает клиентскую часть проекта: что уже есть (каркас из задачи 3 спринта 3), как её
запускать и как добавлять страницы. Серверная часть — в [`README.md`](../README.md), план
следующих экранов — в [`docs/sprint-4-plan.md`](sprint-4-plan.md), алгоритм таймера — в
[`docs/timer.md`](timer.md).

## 1. Что уже есть и чего ещё нет

Есть: проект Vite + React + TypeScript, роутинг на React Router, общий каркас страницы,
две страницы-заготовки (`/login`, `/recipes/:recipeId`), страница 404, 8 тестов маршрутизации,
линт/формат/типы в CI, рабочий `frontend/Dockerfile`.

Нет (сознательно, это следующие задачи спринта 4): вёрстки и CSS, UI-библиотеки, вызовов API,
авторизации, экрана таймеров. Форма входа пока ничего не отправляет, страница рецепта показывает
только id из адреса — так задачу 3 можно проверить тестами, не поднимая бэкенд.

## 2. Стек и почему именно он

| Что | Версия | Почему |
|---|---|---|
| React | 19.3.1 | актуальная версия, нужна для React Router 7 |
| React Router | 7.18.5 | декларативный режим (`BrowserRouter`/`Routes`/`Route`) достаточно для двух страниц; data-API можно включить позже без смены библиотеки |
| Vite | 8.3.8 | быстрый dev-сервер и сборка, первым классом поддерживает TypeScript и React |
| TypeScript | **5.9.3** | `typescript-eslint@8` заявляет peer `typescript >=4.8.4 <6.1.0`; с TypeScript 7 линт не работает, поэтому версия зафиксирована на последней 5.x |
| Vitest + Testing Library | 5.1.0 / 16.3.3 | тесты идут в том же Vite-конфиге, без второго сборщика; jsdom даёт DOM без браузера |
| ESLint + Prettier | 10.14.0 / 3.10.1 | те же роли, что `ruff`/`black` в бэкенде; ширина строки 100 совпадает с `backend/pyproject.toml` |

CRA (Create React App) не используется: он не поддерживается и несовместим с React 19.

## 3. Запуск и проверки

```bash
cd frontend
npm ci                  # ставит ровно то, что в package-lock.json
npm run dev             # http://localhost:3000
npm run test:run        # тесты один раз (vitest run)
npm test                # тесты в watch-режиме
npm run typecheck       # tsc -b (строгий режим)
npm run lint            # eslint
npm run format:check    # prettier --check
npm run build           # tsc -b + vite build → dist/
```

Требуется Node **>= 22.12** (`engines` в `package.json`): этого требуют Vite 8 и Vitest 5.

Через Docker (как в `docker-compose.yml`):

```bash
docker compose up -d backend frontend   # фронтенд на том же порту 3000
docker compose logs -f frontend
```

### Почему именно порт 3000

`CORS_ORIGINS` в `.env.example` и `docker-compose.yml` равен `http://localhost:3000`. Если Vite
займёт другой порт, браузер заблокирует все будущие запросы к API, поэтому в
`vite.config.ts` стоит `strictPort: true` — сервер лучше упадёт с понятной ошибкой, чем молча

## 4. Карта `src/`

```
src/
├── app/routes.ts            # единственное место с адресами + recipePath(id)
├── components/
│   └── AppLayout.tsx        # шапка, навигация, <Outlet /> — каркас всех страниц
├── pages/
│   ├── LoginPage.tsx        # /login: форма без отправки
│   ├── RecipePage.tsx       # /recipes/:recipeId: id из адреса
│   └── NotFoundPage.tsx     # *: 404 и ссылка на вход
├── test/setup.ts            # jest-dom + очистка DOM между тестами
├── __tests__/routing.test.tsx
├── App.tsx                  # только <Routes>: таблица маршрутов
├── main.tsx                 # createRoot + BrowserRouter
└── vite-env.d.ts            # типы import.meta.env от Vite
```

Правило то же, что в бэкенде (CONTRIBUTION.md §2): слои, а не «всё в одном файле». Адреса не
пишутся строками по коду — только через `ROUTES`/`recipePath()`; при переименовании пути компилятор
покажет все ссылки.

## 5. Маршруты и как добавить страницу

| Путь | Компонент | Поведение |
|---|---|---|
| `/` | `<Navigate to="/login" replace />` | главной пока нет |
| `/login` | `LoginPage` | форма входа (заглушка) |
| `/recipes/:recipeId` | `RecipePage` | id рецепта из адреса |
| `*` | `NotFoundPage` | 404 внутри общего каркаса |

Пять шагов для новой страницы:

1. создать `src/pages/NamePage.tsx` (по умолчанию `export default`);
2. добавить путь в `ROUTES` в `src/app/routes.ts` (если путь с параметром — ещё и функцию вида
   `recipePath()`, чтобы никто не склеивал строки вручную);
3. добавить `<Route path={ROUTES.name} element={<NamePage />} />` внутрь
   `<Route element={<AppLayout />}>` в `src/App.tsx`;
4. поставить ссылку через `<Link to={...}>` в `AppLayout` или на странице;
5. добавить кейс в `src/__tests__/routing.test.tsx`: адрес открывает страницу, а неизвестный
   адрес по-прежнему даёт 404.

## 6. Тесты

`src/__tests__/routing.test.tsx` — 8 кейсов, по одному на обещание роутера:

1. `/login` рендерит форму входа (поля email/пароль с правильными типами);
2. `/recipes/42` передаёт `42` в страницу рецепта;
3. на странице рецепта нет формы входа;
4. `/` перенаправляет на `/login`;
5. неизвестный адрес — страница 404 со ссылкой на вход;
6. `/recipes/` без id — тоже 404;
7. ссылка «Вход» в шапке действительно переводит на `/login`;
8. каркас (заголовок и навигация) есть на каждой странице.

Тесты не ходят в сеть и не поднимают браузер: `MemoryRouter` задаёт адрес в памяти, jsdom даёт
DOM, `@testing-library/user-event` имитирует клик. Порог покрытия для фронтенда пока не задан:
пока в коде нет логики, кроме таблицы маршрутов, процент ничего не измеряет; порог появится
вместе с API-клиентом (спринт 4).

## 7. Соглашения TypeScript

- `strict: true` плюс `noUnusedLocals`/`noUnusedParameters` — как в бэкенде, где включены типы.
- Параметры маршрута типизируются на месте: `useParams<{ recipeId: string }>()`; отсутствие
  параметра — это 404, а не `undefined`, который потом утечёт в запрос.
- DTO API описываются `interface` в `src/api/types.ts` **по схемам `openapi.yaml`**, а не по
  памяти; при расхождении прав код, а не контракт (его проверяют контрактные тесты бэкенда).
- Никаких `any`: для неизвестного JSON — `unknown` и явная проверка.
- Path-алиасы (`@/`) не заведены: на десяти файлах они добавляют конфиг в двух местах
  (`vite.config.ts` и `tsconfig`), а пользу приносят только на большом проекте.

## 8. Границы задачи 3

Задача 3 спринта 3 — только каркас и роутинг. Вёрстка, стили, формы с отправкой, авторизация и
экран таймеров — задачи 1–3 спринта 4 ([`docs/sprint-4-plan.md`](sprint-4-plan.md)). Бэкенд при
этом уже готов: `POST /timers`, `GET /timers/active`, `DELETE /timers/{id}` и схема `Timer` из
`openapi.yaml`, а алгоритм отсчёта зафиксирован в [`docs/timer.md`](timer.md) §5.

переедет на 3001.
