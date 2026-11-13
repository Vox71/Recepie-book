import { ArrowRight, Leaf } from 'lucide-react';

import loginHero from '../assets/login-hero.svg';
import Button from '../components/ui/Button';
import PasswordField from '../components/ui/PasswordField';
import TextField from '../components/ui/TextField';
import styles from './LoginPage.module.css';

/**
 * Login screen of the mockup `frontend/design/03 — Вход.png` (sprint 3, task 4).
 *
 * The page is layout only: the form does not call `POST /login` yet (that is the next
 * frontend task, docs/sprint-4-plan.md), so submitting prevents the default browser
 * navigation and nothing leaves the page. The password field does work: its eye button
 * switches the input type and reports the state through `aria-pressed`.
 */
export default function LoginPage() {
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

        <form className={styles.form} onSubmit={(event) => event.preventDefault()}>
          <TextField
            id="email"
            name="email"
            label="Email"
            type="email"
            autoComplete="email"
            placeholder="anna@example.com"
            required
          />
          <PasswordField
            id="password"
            name="password"
            label="Пароль"
            autoComplete="current-password"
            placeholder="••••••••"
            required
          />
          <Button type="submit" fullWidth icon={<ArrowRight size={18} />}>
            Войти
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
