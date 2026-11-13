import { Outlet } from 'react-router-dom';

import SiteFooter from './SiteFooter';
import SiteHeader from './SiteHeader';
import styles from './Layout.module.css';

/**
 * Frame of the login screen: a header without navigation and a footer with the copyright.
 * The page itself fills the space between them, so the footer always touches the bottom.
 */
export default function AuthLayout() {
  return (
    <div className={styles.page}>
      <SiteHeader variant="auth" />
      <main className={styles.main}>
        <Outlet />
      </main>
      <SiteFooter variant="auth" />
    </div>
  );
}
