import styles from './SiteFooter.module.css';

export type FooterVariant = 'auth' | 'app';

interface SiteFooterProps {
  variant: FooterVariant;
}

/**
 * Footer of the mockups. The login screen has the copyright on the left and the phrase on
 * the right; the app screens put the wordmark in the middle of a three-column row.
 */
export default function SiteFooter({ variant }: SiteFooterProps) {
  return (
    <footer className={styles.footer} data-variant={variant}>
      {variant === 'auth' ? (
        <div className={styles.inner}>
          <p className={styles.copy}>© 2026 Recepie Book</p>
          <p className={styles.note}>Хорошая еда начинается с дома</p>
        </div>
      ) : (
        <div className={`${styles.inner} ${styles.innerApp}`}>
          <p className={styles.wordmark}>Recepie Book</p>
          <p className={styles.note}>Меньше лишних покупок. Больше вкусных идей.</p>
          <p className={`${styles.copy} ${styles.copyRight}`}>© 2026</p>
        </div>
      )}
    </footer>
  );
}
