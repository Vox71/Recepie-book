import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from '../App';
import { TOKEN_STORAGE_KEY } from '../auth/AuthContext';

/**
 * Login screen: the layout of `frontend/design/03 — Вход.png` and the real `POST /login`.
 *
 * `fetch` is replaced, so the cases check the form's promises without a network: a
 * successful login stores the token and opens the fridge, a 401 shows a readable message,
 * the password toggle and the disabled registration controls stay intact.
 */
function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <App />
    </MemoryRouter>,
  );
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

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

  it('logs in, stores the token and opens the fridge', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/login')) {
        return jsonResponse({ token: 'jwt-token' });
      }
      return jsonResponse([]);
    });
    vi.stubGlobal('fetch', fetchMock);
    renderLogin();

    await user.type(screen.getByLabelText('Email'), 'anna@example.com');
    await user.type(screen.getByLabelText('Пароль'), 'sup3r-secret');
    await user.click(screen.getByRole('button', { name: 'Войти' }));

    expect(await screen.findByRole('heading', { name: 'Мой холодильник' })).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_STORAGE_KEY)).toBe('jwt-token');
  });

  it('shows a readable message when the credentials are wrong', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ error: 'Invalid email or password' }, 401)),
    );
    renderLogin();

    await user.type(screen.getByLabelText('Email'), 'anna@example.com');
    await user.type(screen.getByLabelText('Пароль'), 'wrong-password');
    await user.click(screen.getByRole('button', { name: 'Войти' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Неверный email или пароль');
    expect(screen.getByRole('heading', { name: 'С возвращением!' })).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
  });

  it('marks both registration controls as unavailable', () => {
    renderLogin();

    const controls = screen.getAllByRole('button', { name: 'Создать аккаунт' });

    expect(controls).toHaveLength(2); // the header link and the line under the form
    for (const control of controls) {
      expect(control).toHaveAttribute('aria-disabled', 'true');
    }
  });

  it('shows the server error when login fails for another reason', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ error: 'Server is down' }, 500)),
    );
    renderLogin();

    await user.type(screen.getByLabelText('Email'), 'anna@example.com');
    await user.type(screen.getByLabelText('Пароль'), 'sup3r-secret');
    await user.click(screen.getByRole('button', { name: 'Войти' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Server is down');
  });

  it('shows the footer of the login screen', () => {
    renderLogin();

    expect(screen.getByText('© 2026 Recepie Book')).toBeInTheDocument();
    expect(screen.getByText('Хорошая еда начинается с дома')).toBeInTheDocument();
    expect(screen.getByText('Вдохновение для вашей повседневной кухни')).toBeInTheDocument();
  });
});
