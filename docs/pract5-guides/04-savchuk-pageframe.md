# Савчук Иван, вариант 5: пошаговая инструкция

**Ветка:** `refactor/pract5-pageframe`

**Файлы:**

- `frontend/src/components/layout/PageFrame.tsx` — новый файл;
- `frontend/src/components/layout/AppLayout.tsx`;
- `frontend/src/components/layout/AuthLayout.tsx`.

**Что должно получиться:** общий каркас страницы в `PageFrame`, два старых layout-файла стали
короткими обёртками. Разметка и стили не меняются.

## Шаг 1. Подготовить ветку

```bash
git switch main
git pull
git switch -c refactor/pract5-pageframe
git status
```

## Шаг 2. Создать `PageFrame.tsx`

Новый файл `frontend/src/components/layout/PageFrame.tsx`:

```tsx
import { Outlet } from 'react-router-dom';

import SiteFooter from './SiteFooter';
import SiteHeader from './SiteHeader';
import styles from './Layout.module.css';

export type PageVariant = 'auth' | 'app';

export interface PageFrameProps {
  variant: PageVariant;
}

/**
 * Common frame of every page: header, the page itself and the footer.
 * The variant picks the header/footer of the login screen or of the app.
 */
export default function PageFrame({ variant }: PageFrameProps) {
  return (
    <div className={styles.page}>
      <SiteHeader variant={variant} />
      <main className={styles.main}>
        <Outlet />
      </main>
      <SiteFooter variant={variant} />
    </div>
  );
}
```

Здесь важен `Outlet`: через него React Router показывает содержимое страницы между шапкой и
подвалом.

## Шаг 3. Заменить `AuthLayout.tsx`

Файл `frontend/src/components/layout/AuthLayout.tsx` полностью заменить на:

```tsx
import PageFrame from './PageFrame';

/**
 * Frame of the login screen: header without navigation and the copyright footer.
 */
export default function AuthLayout() {
  return <PageFrame variant="auth" />;
}
```

## Шаг 4. Заменить `AppLayout.tsx`

Файл `frontend/src/components/layout/AppLayout.tsx` полностью заменить на:

```tsx
import PageFrame from './PageFrame';

/**
 * Frame of the signed-in screens: pill navigation, user menu and the three-column footer.
 */
export default function AppLayout() {
  return <PageFrame variant="app" />;
}
```

## Шаг 5. Проверить импорты

В старых layout-файлах не должно остаться:

- `Outlet`;
- `SiteHeader`;
- `SiteFooter`;
- `Layout.module.css`.

Эти импорты теперь только в `PageFrame.tsx`.

`App.tsx`, `SiteHeader.tsx`, `SiteFooter.tsx`, `Layout.module.css` и тесты не меняются.

## Шаг 6. Проверить

```bash
cd frontend
npm ci
npm run format:check
npm run lint
npm run typecheck
npm run test:coverage
npm run build
```

Ожидаемо: тесты проходят, сборка без ошибок. Если `format:check` ругается, выполнить
`npm run format` и проверить diff.

## Шаг 7. Коммит и push

```bash
git diff --stat
git diff --check
git add frontend/src/components/layout/PageFrame.tsx
git add frontend/src/components/layout/AppLayout.tsx frontend/src/components/layout/AuthLayout.tsx
git commit -m "refactor(layout): extract common page frame"
git push -u origin refactor/pract5-pageframe
```

Если `git diff --stat` показывает изменения в CSS или тестах, их нужно убрать из индекса.

## Шаг 8. PR

Заголовок:

```text
refactor(layout): extract common page frame
```

В описании:

- было: две почти одинаковые разметки, дублирование около 90 %;
- стало: один `PageFrame` и две обёртки;
- поведение и тесты не меняются;
- проверки: `format:check`, `lint`, `typecheck`, `test:coverage`, `build`.

Ревьюер: Тропина Елизавета.

## Частые ошибки

- `PageFrame` импортирует `Outlet`, но старый layout тоже остался с `Outlet`;
- в `AuthLayout` или `AppLayout` забыт `import PageFrame`;
- изменены `SiteHeader`/`SiteFooter`, хотя их трогать не нужно;
- в коммит попал `Layout.module.css`.

## Правки после раунда 1

Ревьюер попросил расположить тип и интерфейс рядом и вернуть пояснение про футер.

В `PageFrame.tsx`:

```tsx
export type PageVariant = 'auth' | 'app';

export interface PageFrameProps {
  variant: PageVariant;
}

/**
 * Common frame of every page: header, the page itself and the footer.
 * The variant picks the header/footer of the login screen or of the app.
 * The page inside <main> stretches, so the footer stays at the bottom.
 */
export default function PageFrame({ variant }: PageFrameProps) {
```

Если `type` и `interface` уже стоят рядом, меняется только комментарий. После правки:

```bash
git add frontend/src/components/layout/PageFrame.tsx
git commit -m "docs(layout): explain the page frame footer"
git push
```
