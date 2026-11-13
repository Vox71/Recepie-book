import { Outlet } from 'react-router-dom';

import SiteFooter from './SiteFooter';
import SiteHeader from './SiteHeader';
import styles from './Layout.module.css';

/**
 * Frame of the signed-in screens: header with the pill navigation and the user menu, then
 * the page, then the three-column footer. `/recipes/:id` and the 404 page live here; the
 * login screen uses `AuthLayout`, because the mockup gives it another header.
 */
export default function AppLayout() {
  return (
    <div className={styles.page}>
      <SiteHeader variant="app" />
      <main className={styles.main}>
        <Outlet />
      </main>
      <SiteFooter variant="app" />
    </div>
  );
}
