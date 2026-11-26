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