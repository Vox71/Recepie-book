import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import App from '../App';

/**
 * Login screen (sprint 3, task 4): the layout of `frontend/design/03 — Вход.png`.
 *
 * The form has no API yet, so the cases check what the page really promises today: the
 * greeting and the copy of the mockup, a working password toggle, a submit that does not
 * leave the page, and the registration control that is honestly marked as unavailable.
 */
function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <App />
    </MemoryRouter>,
  );
}

describe('login page', () => {
  it('shows the greeting, the subtitle and the form', () => {
    renderLogin();

    expect(screen.getByRole('heading', { name: 'С возвращением!' })).toBeInTheDocument();
    expect(
      screen.getByText('Войдите, чтобы вернуться к своему холодильнику и любимым рецептам.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Войти' })).toHaveAttribute('type', 'submit');
  });

  it('shows the promises of the hero card', () => {
    renderLogin();

    expect(screen.getByText('Готовьте из того, что уже есть')).toBeInTheDocument();
    expect(screen.getByText('просто. вкусно. по-домашнему.')).toBeInTheDocument();
    expect(
      screen.getByText('Любимые продукты, новые сочетания и маленькая радость от домашнего ужина.'),
    ).toBeInTheDocument();
  });

  it('switches the password visibility and reports the state', async () => {
    const user = userEvent.setup();
    renderLogin();
    const password = screen.getByLabelText('Пароль');
    const show = screen.getByRole('button', { name: 'Показать пароль' });

    expect(password).toHaveAttribute('type', 'password');
    expect(show).toHaveAttribute('aria-pressed', 'false');

    await user.click(show);

    expect(password).toHaveAttribute('type', 'text');
    const hide = screen.getByRole('button', { name: 'Скрыть пароль' });
    expect(hide).toHaveAttribute('aria-pressed', 'true');

    await user.click(hide);

    expect(password).toHaveAttribute('type', 'password');
  });

  it('does not leave the page on submit (there is no API yet)', async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText('Email'), 'anna@example.com');
    await user.type(screen.getByLabelText('Пароль'), 'sup3r-secret');
    await user.click(screen.getByRole('button', { name: 'Войти' }));

    expect(screen.getByRole('heading', { name: 'С возвращением!' })).toBeInTheDocument();
  });

  it('marks both registration controls as unavailable', () => {
    renderLogin();

    const controls = screen.getAllByRole('button', { name: 'Создать аккаунт' });

    expect(controls).toHaveLength(2); // the header link and the line under the form
    for (const control of controls) {
      expect(control).toHaveAttribute('aria-disabled', 'true');
    }
  });

  it('shows the footer of the login screen', () => {
    renderLogin();

    expect(screen.getByText('© 2026 Recepie Book')).toBeInTheDocument();
    expect(screen.getByText('Хорошая еда начинается с дома')).toBeInTheDocument();
    expect(screen.getByText('Вдохновение для вашей повседневной кухни')).toBeInTheDocument();
  });
});
