import { ArrowRight, Leaf } from 'lucide-react';
import { useState } from 'react';
import type { FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import { ROUTES } from '../app/routes';
import loginHero from '../assets/login-hero.svg';
import { useAuth } from '../auth/AuthContext';
import Button from '../components/ui/Button';
import PasswordField from '../components/ui/PasswordField';
import TextField from '../components/ui/TextField';
import styles from './LoginPage.module.css';

interface LoginLocationState {
  from?: string;
}

/**
 * Login screen of the mockup `frontend/design/03 — Вход.png`.
 *
 * The form calls `POST /login`, stores the JWT through `AuthProvider` and returns the
 * user to the page they tried to open.  A 401 is shown as a readable message, not as a
 * raw API error; the password visibility toggle stays local to the field.
 */
export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      const state = location.state as LoginLocationState | null;
      navigate(state?.from ?? ROUTES.fridge, { replace: true });
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        setError('Неверный email или пароль');
      } else {
        setError(cause instanceof Error ? cause.message : 'Не удалось войти');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.layout}>
      <section className={styles.hero} aria-label="О приложении">
        <img className={styles.heroImage} src={loginHero} alt="" />
        <div className={styles.heroOverlay} aria-hidden="true" />
        <div className={styles.heroContent}>
          <p className={styles.heroKicker}>
            <Leaf size={16} aria-hidden="true" />
            просто. вкусно. по-домашнему.
          </p>
          <p className={styles.heroTitle}>Готовьте из того, что уже есть</p>
          <p className={styles.heroText}>
            Любимые продукты, новые сочетания и маленькая радость от домашнего ужина.
          </p>
        </div>
      </section>

      <section className={styles.panel} aria-labelledby="login-title">
        <p className={styles.eyebrow}>Рады вас видеть</p>
        <h1 id="login-title" className={styles.title}>
          С возвращением!
        </h1>
        <p className={styles.subtitle}>
          Войдите, чтобы вернуться к своему холодильнику и любимым рецептам.
        </p>

        <form className={styles.form} onSubmit={handleSubmit}>
          <TextField
            id="email"
            name="email"
            label="Email"
            type="email"
            autoComplete="email"
            placeholder="anna@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
          <PasswordField
            id="password"
            name="password"
            label="Пароль"
            autoComplete="current-password"
            placeholder="••••••••"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
          {error ? (
            <p className={styles.error} role="alert">
              {error}
            </p>
          ) : null}
          <Button type="submit" fullWidth disabled={submitting} icon={<ArrowRight size={18} />}>
            {submitting ? 'Входим…' : 'Войти'}
          </Button>
        </form>

        <p className={styles.signup}>
          Ещё нет аккаунта?{' '}
          <button
            type="button"
            className={styles.signupLink}
            aria-disabled="true"
            title="Регистрация появится позже"
          >
            Создать аккаунт
          </button>
        </p>

        <hr className={styles.divider} />

        <p className={styles.note}>
          <Leaf size={16} aria-hidden="true" />
          Вдохновение для вашей повседневной кухни
        </p>
      </section>
    </div>
  );
}
