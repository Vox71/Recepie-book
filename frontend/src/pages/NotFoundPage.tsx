import { Link } from 'react-router-dom';

import { ROUTES } from '../app/routes';
import styles from './NotFoundPage.module.css';

/**
 * 404 page. It reuses the signed-in layout (mockup 02/04), so an unknown address still has
 * the header and the footer and a way back instead of a blank screen.
 */
export default function NotFoundPage() {
  return (
    <div className={styles.page}>
      <p className={styles.eyebrow}>Ошибка 404</p>
      <h1 className={styles.title}>Страница не найдена</h1>
      <p className={styles.text}>Такого адреса в приложении нет.</p>
      <Link className={styles.link} to={ROUTES.login}>
        Перейти ко входу
      </Link>
    </div>
  );
}
