import { ArrowRight, ChevronDown } from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';

import { ROUTES } from '../../app/routes';
import { useAuth } from '../../auth/AuthContext';
import Logo from '../brand/Logo';
import styles from './SiteHeader.module.css';

export type HeaderVariant = 'auth' | 'app';

const LATER = 'Раздел появится позже';

interface SiteHeaderProps {
  variant: HeaderVariant;
}

/**
 * Header of both frames. The fridge link is real now; the feed and favourites are still
 * buttons marked `aria-disabled`, because those pages do not exist. The active pill is
 * driven by the current address (`aria-current` for the link, `data-active` for the feed).
 */
export default function SiteHeader({ variant }: SiteHeaderProps) {
  const { email, logout } = useAuth();
  const { pathname } = useLocation();
  const feedActive = !pathname.startsWith(ROUTES.fridge);
  const displayName = email ?? 'Аккаунт';
  const initials = email ? email.slice(0, 2).toUpperCase() : 'АК';

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
              <button
                type="button"
                className={styles.navItem}
                data-active={feedActive ? 'true' : undefined}
                aria-disabled="true"
                title={LATER}
              >
                Лента
              </button>
              <NavLink to={ROUTES.fridge} className={styles.navItem}>
                Мой холодильник
              </NavLink>
              <button type="button" className={styles.navItem} aria-disabled="true" title={LATER}>
                Избранное
              </button>
            </nav>
            <div className={styles.user}>
              <span className={styles.userName} title={displayName}>
                {displayName}
              </span>
              <button
                type="button"
                className={styles.userButton}
                onClick={logout}
                aria-label="Выйти"
                title="Выйти"
              >
                <span className={styles.avatar} aria-hidden="true">
                  {initials}
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
