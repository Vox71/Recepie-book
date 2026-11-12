import { useState } from 'react'
import { Link } from 'react-router'
import AuthLayout from '../components/AuthLayout'
import Icon from '../components/Icon'

export default function RegisterPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')

  const passwordsMismatch =
    confirmation.length > 0 && password !== confirmation

  return (
    <AuthLayout registration>

            <p className="eyebrow">Давайте знакомиться</p>
            <h1 id="register-title">Добро пожаловать!</h1>
            <p className="intro">
              Создайте аккаунт, чтобы собрать свою домашнюю книгу рецептов.
            </p>

            <form
              className="login-form"
              onSubmit={(event) => event.preventDefault()}
            >
              <div className="form-field">
                <label htmlFor="register-name">Имя пользователя</label>
                <input
                  id="register-name"
                  name="username"
                  type="text"
                  autoComplete="username"
                  placeholder="Как к вам обращаться?"
                  required
                />
              </div>

              <div className="form-field">
                <label htmlFor="register-email">Email</label>
                <input
                  id="register-email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  placeholder="Введите email"
                  required
                />
              </div>

              <div className="form-field">
                <label htmlFor="register-password">Пароль</label>
                <div className="password-field">
                  <input
                    id="register-password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    placeholder="Придумайте пароль"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                  />
                  <button
                    className="password-toggle"
                    aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                    type="button"
                    aria-controls="register-password register-confirmation"
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((value) => !value)}
                  >
                    <Icon name={showPassword ? 'eye' : 'eyeOff'} size={20}/>
                  </button>
                </div>
              </div>

              <div className="form-field">
                <label htmlFor="register-confirmation">Повторите пароль</label>
                <input
                  id="register-confirmation"
                  name="password_confirmation"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  placeholder="Введите пароль ещё раз"
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                  aria-invalid={passwordsMismatch}
                  aria-describedby={
                    passwordsMismatch ? 'password-error' : undefined
                  }
                  required
                />
                {passwordsMismatch && (
                  <p className="form-error" id="password-error" role="status">
                    Пароли не совпадают.
                  </p>
                )}
              </div>

              <button
                className="primary-button"
                type="submit"
                aria-describedby="register-hint"
                disabled
              >
                Создать аккаунт →
              </button>
              <p className="field-hint" id="register-hint">
                Регистрация станет доступна после подключения сервера.
              </p>
            </form>

            <p className="auth-bottom">
              Уже есть аккаунт? <Link to="/login">Войти</Link>
            </p>
            <p className="login-caption">
              <Icon name="leaf" size={18}/> Хорошая еда начинается с простых идей
            </p>
    </AuthLayout>
  )
}
