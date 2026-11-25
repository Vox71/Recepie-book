# Фронтенд: React, TypeScript, роутинг и дизайн-система

Документ описывает клиентскую часть проекта: что уже есть, как её запускать и как добавлять
страницы. Визуальная часть (токены, компоненты, адаптив) — в
[`docs/design-system.md`](design-system.md). Серверная часть — в [`README.md`](../README.md), план
следующих экранов — в [`docs/sprint-4-plan.md`](sprint-4-plan.md), алгоритм таймера — в
[`docs/timer.md`](timer.md).

## 1. Что уже есть и чего ещё нет

Есть: проект Vite + React + TypeScript, роутинг на React Router, два каркаса страниц (до и после
входа), вёрстка экранов «Вход» и «Рецепт» по макетам `frontend/design/`, 404, дизайн-токены и
UI-примитивы, 29 тестов с измерением покрытия (порог 80 % в CI), линт/формат/типы, рабочий
`frontend/Dockerfile`.

Нет (сознательно, это следующие задачи спринта 4): вызовов API, авторизации, экрана таймеров,
страниц ленты/холодильника/избранного. Форма входа пока ничего не отправляет, страница рецепта
показывает типизированный мок, а ссылки на несуществующие разделы помечены `aria-disabled`.

## 2. Стек и почему именно он

| Что | Версия | Почему |
|---|---|---|
| React | 19.3.1 | актуальная версия, нужна для React Router 7 |
| React Router | 7.18.5 | декларативный режим (`BrowserRouter`/`Routes`/`Route`) достаточно для двух страниц; data-API можно включить позже без смены библиотеки |
| Vite | 8.3.8 | быстрый dev-сервер и сборка, первым классом поддерживает TypeScript и React |
| TypeScript | **5.9.3** | `typescript-eslint@8` заявляет peer `typescript >=4.8.4 <6.1.0`; с TypeScript 7 линт не работает, поэтому версия зафиксирована на последней 5.x |
| CSS Modules | встроены в Vite | области видимости по компонентам без новых зависимостей; токены — в `src/styles/tokens.css` |
| `@fontsource-variable/lora`, `@fontsource-variable/inter` | 5.3.0 | шрифты макета локально, один woff2 на подъязык, без CDN |
| `lucide-react` | 1.72.0 | набор линейных иконок макета, tree-shaking, peer `react ^19` |
| Vitest + Testing Library | 5.1.0 / 16.3.3 | тесты идут в том же Vite-конфиге, без второго сборщика; jsdom даёт DOM без браузера |
| ESLint + Prettier | 10.14.0 / 3.10.1 | те же роли, что `ruff`/`black` в бэкенде; ширина строки 100 совпадает с `backend/pyproject.toml` |

CRA (Create React App) не используется: он не поддерживается и несовместим с React 19.

## 3. Запуск и проверки

```bash
cd frontend
npm ci                  # ставит ровно то, что в package-lock.json
npm run dev             # http://localhost:3000
npm run test:run        # тесты один раз (vitest run)
npm run test:coverage   # те же тесты + покрытие и порог 80 %
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
переедет на 3001.

## 4. Карта `src/`

```
src/
├── app/routes.ts              # единственное место с адресами + recipePath(id)
├── api/                        # fetch-обёртка, /login и /profile/fridge
│   ├── client.ts               # VITE_API_URL, Authorization, ApiError
│   ├── auth.ts                 # POST /login
│   └── fridge.ts               # GET/POST/DELETE /profile/fridge
├── auth/                       # AuthProvider, useAuth, RequireAuth
├── styles/
│   ├── tokens.css             # палитра, типографика, отступы, радиусы, брейкпоинты
│   └── base.css               # reset, body, focus-visible, .sr-only
├── assets/                    # login-hero.svg, recipe-hero.svg (заглушки фото)
├── mocks/recipe.ts            # типизированный мок страницы рецепта (до API)
├── components/
│   ├── layout/                # SiteHeader, SiteFooter, AuthLayout, AppLayout
│   ├── brand/Logo.tsx         # плитка с глифом + серифный вордмарк
│   ├── ui/                    # Button, TextField, PasswordField
│   ├── fridge/                # FridgeSummary, ProductCard, AddProductForm, expiry rules
│   └── recipe/                # Breadcrumbs, RecipeHero, IngredientsCard, StepsList
├── pages/
│   ├── LoginPage.tsx          # /login: макет 03 + POST /login
│   ├── FridgePage.tsx         # /fridge: продукты текущего пользователя
│   ├── RecipePage.tsx         # /recipes/:recipeId: макет 02 на моке
│   └── NotFoundPage.tsx       # *: 404 в каркасе после входа
├── test/setup.ts              # jest-dom + очистка DOM и localStorage между тестами
├── __tests__/                 # routing, login, recipe, fridge, expiry rules, API
├── App.tsx                    # <AuthProvider>, <Routes>, защищённый AppLayout
├── main.tsx                   # шрифты, токены, createRoot + BrowserRouter
└── vite-env.d.ts              # типы import.meta.env от Vite
```

Правило то же, что в бэкенде (CONTRIBUTION.md §2): слои, а не «всё в одном файле». Адреса не
пишутся строками по коду — только через `ROUTES`/`recipePath()`; при переименовании пути компилятор
покажет все ссылки. Стили — CSS Modules рядом с компонентом, значения — только из токенов
([`docs/design-system.md`](design-system.md) §6).

## 5. Маршруты и как добавить страницу

| Путь | Компонент | Каркас | Поведение |
|---|---|---|---|
| `/` | `<Navigate to="/login" replace />` | — | главной пока нет |
| `/login` | `LoginPage` | `AuthLayout` | макет 03: `POST /login`, токен в `localStorage`, переход на `/fridge` |
| `/recipes/:recipeId` | `RecipePage` | `AppLayout` (под защитой) | макет 02: id из адреса, данные из мока |
| `/fridge` | `FridgePage` | `AppLayout` (под защитой) | `GET/POST/DELETE /profile/fridge`; продукты только из токена |
| `*` | `NotFoundPage` | `AppLayout` (под защитой) | 404 со ссылкой на вход |

`/recipes/:recipeId`, `/fridge` и 404 обёрнуты в `RequireAuth`: без токена пользователь
попадает на `/login`, а после входа возвращается на запрошенный адрес.

### Авторизация и токен

`AuthProvider` (`src/auth/AuthContext.tsx`) хранит JWT в `localStorage` под ключом
`recepie-book.token`; `apiRequest` добавляет `Authorization: Bearer <token>` ко всем запросам.
Любой ответ 401 в защищённом интерфейсе очищает токен и возвращает на `/login`. Пароль нигде не
хранится; после выхода остаётся только гость.

Пять шагов для новой страницы:

1. создать `src/pages/NamePage.tsx` и `NamePage.module.css` (по умолчанию `export default`);
2. добавить путь в `ROUTES` в `src/app/routes.ts` (если путь с параметром — ещё и функцию вида
   `recipePath()`, чтобы никто не склеивал строки вручную);
3. добавить `<Route path={ROUTES.name} element={<NamePage />} />` внутрь нужного лейаута
   (`AuthLayout` или `AppLayout`) в `src/App.tsx`;
4. поставить ссылку через `<Link to={...}>`: если раздела ещё нет, оставить кнопку с
   `aria-disabled`, как в шапке;
5. добавить кейс в `src/__tests__/`: адрес открывает страницу, а неизвестный адрес по-прежнему
   даёт 404.

## 6. Тесты

**49 кейсов в семи файлах**, все без сети и без браузера (`MemoryRouter` + jsdom; `fetch`
подменяется в тестах самих страниц):

- `routing.test.tsx` (13) — `/login`, `/recipes/42`, `/fridge`, `/`, 404, логотип,
  шапка/подвал, редирект неавторизованного пользователя;
- `login-page.test.tsx` (8) — макет, переключение пароля, успешный `POST /login`
  (токен + переход на холодильник), 401 и 500 с понятными сообщениями, подвал;
- `recipe-page.test.tsx` (10) — заголовок и мета, ингредиенты, аллергены, шаги,
  источник, избранное, крошки, навигация (холодильник — рабочая ссылка), подвал;
- `fridge-page.test.tsx` (12) — сводка, список, фильтры, пустые состояния, добавление,
  удаление, удаление просроченных, ошибки загрузки/добавления/удаления, 401;
- `fridge-status.test.ts` (2) — статусы «свежий/скоро/просрочен», дата и подсказки;
- `routes.test.ts` (2) — `recipePath()`: адрес из id и экранирование спецсимволов;
- `components.test.tsx` (2) — `Button` без иконки, карточка ингредиентов без аллергенов.


Покрытие измеряется и проверяется в CI:

```bash
npm run test:coverage   # Vitest v8, порог 80 % (statements/branches/functions/lines)
```

Измерено 25.11.2026: **93,14 % statements, 85,80 % branches, 98,90 % functions, 92,80 % lines**;
`main.tsx`, `test/**`, `mocks/**`, `assets/**`, `vite-env.d.ts` и сами тесты исключены — причины
и оговорка «100 % ≠ UI проверен» в [`docs/test-coverage.md`](test-coverage.md) §2.11.

## 7. Соглашения TypeScript и CSS

- `strict: true` плюс `noUnusedLocals`/`noUnusedParameters` — как в бэкенде, где включены типы.
- Параметры маршрута типизируются на месте: `useParams<{ recipeId: string }>()`; отсутствие
  параметра — это 404, а не `undefined`, который потом утечёт в запрос.
- DTO API описываются `interface` в `src/api/types.ts` **по схемам `openapi.yaml`**, а не по
  памяти; при расхождении прав код, а не контракт (его проверяют контрактные тесты бэкенда).
- Никаких `any`: для неизвестного JSON — `unknown` и явная проверка.
- CSS: один `Component.module.css` на компонент, в нём только `var(--…)` и `@media`; глобальных
  классов нет, кроме `.sr-only`.
- Path-алиасы (`@/`) не заведены: на десяти файлах они добавляют конфиг в двух местах
  (`vite.config.ts` и `tsconfig`), а пользу приносят только на большом проекте.

## 8. Границы задач 3 и 4

Задача 3 — каркас и роутинг, задача 4 — вёрстка двух экранов. Ветка `feat/fridge-auth`
добавила API-клиент, авторизацию, защиту маршрутов и страницу «Мой холодильник»:
`POST /login`, `GET/POST/DELETE /profile/fridge`, токен в `localStorage`. Остальные страницы
(лента, избранное, таймеры) — следующие задачи спринта 4 ([`docs/sprint-4-plan.md`](sprint-4-plan.md)).
