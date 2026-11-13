import { Link } from 'react-router-dom';

import { ROUTES } from '../../app/routes';
import styles from './Logo.module.css';

/**
 * Brand lockup of the mockups: a dark green tile with the spoon glyph plus the serif
 * wordmark. The link leads to `/`, which currently redirects to the login screen.
 *
 * The glyph is drawn here (the mockup has no exported SVG): if the designer sends the
 * real mark, only the `<svg>` below is replaced.
 */
export default function Logo() {
  return (
    <Link className={styles.logo} to={ROUTES.home}>
      <span className={styles.mark} aria-hidden="true">
        <svg viewBox="0 0 32 32" width="22" height="22" fill="none" stroke="currentColor">
          <path
            d="M12.5 8.5c-4.1 0-7.4 3.3-7.4 7.4s3.3 7.4 7.4 7.4c2 0 3.9-.8 5.2-2.2"
            strokeWidth="1.7"
            strokeLinecap="round"
          />
          <path
            d="M18 7.5v12.8c0 2.2 1.5 3.9 3.7 3.9s3.7-1.7 3.7-3.9c0-2-1.3-3.3-3.3-4.2L18 14.3"
            strokeWidth="1.7"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <span className={styles.wordmark}>Recepie Book</span>
    </Link>
  );
}
