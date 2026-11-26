# Савчук Иван, вариант 5

**Ветка:** `refactor/pract5-pageframe`

**Файлы:** `frontend/src/components/layout/AppLayout.tsx`,
`frontend/src/components/layout/AuthLayout.tsx`, новый
`frontend/src/components/layout/PageFrame.tsx`.

## Что делаем

`AppLayout` и `AuthLayout` отличаются только вариантом шапки и подвала. Остальная разметка
одинаковая. Выносим её в `PageFrame`, а старые файлы оставляем короткими обёртками.

## Как делать

1. Создай `PageFrame.tsx`:

   ```tsx
   import { Outlet } from 'react-router-dom';

   import SiteFooter from './SiteFooter';
   import SiteHeader from './SiteHeader';
   import styles from './Layout.module.css';

   export type PageVariant = 'auth' | 'app';

   export default function PageFrame({ variant }: { variant: PageVariant }) {
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

2. `AuthLayout.tsx`:

   ```tsx
   import PageFrame from './PageFrame';

   export default function AuthLayout() {
     return <PageFrame variant="auth" />;
   }
   ```

3. `AppLayout.tsx` — так же, но `variant="app"`.
4. Убедись, что из старых файлов ушли `Outlet`, `SiteHeader`, `SiteFooter` и CSS-модуль.
5. Проверь:

   ```bash
   cd frontend
   npm ci
   npm run format:check
   npm run lint
   npm run typecheck
   npm run test:coverage
   npm run build
   ```

## Что писать в PR

Заголовок:

```text
refactor(layout): extract common page frame
```

В описании: две почти одинаковые разметки, дублирование около 90 %. Теперь один `PageFrame` и
две обёртки. Поведение и тесты не меняются.

## Что может спросить ревьюер

- «Почему `variant` строкой, а не отдельными компонентами?» — вариантов всего два, и они уже
  поддержаны в `SiteHeader`/`SiteFooter`; так проще.
- «Почему не вынес `main` в отдельный компонент?» — это одна строка, отдельный компонент только
  добавит файлов.
- «Не сломалась ли типизация?» — `PageVariant` ограничивает значения, `tsc` это проверит.

## Не трогай

`App.tsx`, `SiteHeader.tsx`, `SiteFooter.tsx`, `Layout.module.css` и тесты. Меняются только три
файла layout.
