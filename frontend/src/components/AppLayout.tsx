import { Link, Outlet } from 'react-router-dom';

import { ROUTES, recipePath } from '../app/routes';

/**
 * Frame of every page: the name of the application, two links and the page itself.
 *
 * There is deliberately no styling and no design system yet (task 3 is only the skeleton
 * and the routing). The links exist so the navigation can be clicked and tested; the
 * "example recipe" link is the shortest way to reach the recipe screen by hand.
 */
export default function AppLayout() {
  return (
    <div>
      <header>
        <h1>Recepie-book</h1>
        <nav aria-label="Основная навигация">
          <Link to={ROUTES.login}>Вход</Link>
          {' · '}
          <Link to={recipePath(1)}>Пример рецепта</Link>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
