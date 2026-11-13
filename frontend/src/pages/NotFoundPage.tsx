import { Link } from 'react-router-dom';

import { ROUTES } from '../app/routes';

/**
 * 404 page: an unknown address is answered with a page and a way back, not with a blank
 * screen. It sits inside `AppLayout`, so the navigation stays usable.
 */
export default function NotFoundPage() {
  return (
    <section>
      <h2>Страница не найдена</h2>
      <p>Такого адреса в приложении нет.</p>
      <Link to={ROUTES.login}>Перейти ко входу</Link>
    </section>
  );
}
