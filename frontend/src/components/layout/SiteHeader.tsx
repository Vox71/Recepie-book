import { ArrowRight, ChevronDown } from 'lucide-react';

import Logo from '../brand/Logo';
import styles from './SiteHeader.module.css';

export type HeaderVariant = 'auth' | 'app';

/**
 * Navigation items of the mockup. The pages behind them (feed, fridge, favourites) do not
 * exist yet, so they are buttons marked `aria-disabled` instead of links to nowhere:
 * a click does nothing and a screen reader announces them as unavailable. When the pages
 * arrive, these become `<Link>` and the markup of the header does not change.
 */
const NAV_ITEMS = [
  { label: 'Лента', active: true },
  { label: 'Мой холодильник', active: false },
  { label: 'Избранное', active: false },
] as const;

const LATER = 'Раздел появится позже';

interface SiteHeaderProps {
  variant: HeaderVariant;
}

export default function SiteHeader({ variant }: SiteHeaderProps) {
  return (
    <header className={styles.header} data-variant={variant}>
      <div className={styles.inner}>
        <Logo />
        {variant === 'auth' ? (
          <p className={styles.authAction}>
            <span className={styles.authQuestion}>Впервые здесь?</span>
            <button
              type="button"
              className={styles.authLink}
              aria-disabled="true"
              title="Регистрация появится позже"
            >
              Создать аккаунт
              <ArrowRight size={16} aria-hidden="true" />
            </button>
          </p>
        ) : (
          <>
            <nav className={styles.nav} aria-label="Основная навигация">
              {NAV_ITEMS.map((item) => (
                <button
                  key={item.label}
                  type="button"
                  className={styles.navItem}
                  data-active={item.active ? 'true' : undefined}
                  aria-disabled="true"
                  title={LATER}
                >
                  {item.label}
                </button>
              ))}
            </nav>
            <div className={styles.user}>
              <span className={styles.userName}>Анна</span>
              <button
                type="button"
                className={styles.userButton}
                aria-label="Меню пользователя Анна"
                aria-disabled="true"
                title="Меню пользователя появится позже"
              >
                <span className={styles.avatar} aria-hidden="true">
                  АК
                </span>
                <ChevronDown size={16} aria-hidden="true" />
              </button>
            </div>
          </>
        )}
      </div>
    </header>
  );
}
