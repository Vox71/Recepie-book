import { useState } from 'react'
import { Link } from 'react-router'
import AuthLayout from '../components/AuthLayout'
import Icon from '../components/Icon'

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)

  return (
    <AuthLayout>

            <p className="eyebrow">Рады вас видеть</p>
            <h1 id="login-title">С возвращением!</h1>
            <p className="intro">
              Войдите, чтобы вернуться к своему холодильнику
              и любимым рецептам.
            </p>

            <form
              className="login-form"
              onSubmit={(event) => event.preventDefault()}
            >
              <div className="form-field">
                <label htmlFor="email">Email</label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="username"
                  placeholder="Введите email"
                  required
                />
              </div>

              <div className="form-field">
                <label htmlFor="password">Пароль</label>
                <div className="password-field">
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    placeholder="Введите пароль"
                    required
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                    aria-controls="password"
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((value) => !value)}
                  >
                    <Icon name={showPassword ? 'eye' : 'eyeOff'} size={20}/>
                  </button>
                </div>
              </div>

              <button
                className="primary-button"
                type="submit"
                aria-describedby="login-hint"
                disabled
              >
                Войти →
              </button>
              <p className="field-hint" id="login-hint">
                Вход станет доступен после подключения авторизации.
              </p>
            </form>

            <p className="auth-bottom">
              Ещё нет аккаунта? <Link to="/register">Создать аккаунт</Link>
            </p>
            <p className="login-caption">
              <Icon name="leaf" size={18}/> Вдохновение для вашей повседневной кухни
            </p>
    </AuthLayout>
  )
}
