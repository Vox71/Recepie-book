import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from '../App';
import { TOKEN_STORAGE_KEY } from '../auth/AuthContext';

/**
 * Routing tests (sprint 3, task 3) after the design of task 4.
 *
 * Every case pins one promise of `src/App.tsx`: which page is rendered for an address,
 * that `/` redirects to the login screen, that an unknown address is a 404 page in the
 * signed-in frame, and that each frame carries its own header and footer. The tests use
 * roles and accessible names, so a restyle does not break them - only a changed text does.
 * `MemoryRouter` keeps everything in memory: no history, no reload, no network.
 */
function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
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

beforeEach(() => {
  window.localStorage.setItem(TOKEN_STORAGE_KEY, 'test-token');
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const loginHeading = () => screen.getByRole('heading', { name: 'С возвращением!' });
const notFoundHeading = () => screen.getByRole('heading', { name: 'Страница не найдена' });

describe('app routing', () => {
  it('renders the login page at /login', () => {
    renderAt('/login');

    expect(loginHeading()).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toHaveAttribute('type', 'email');
    expect(screen.getByLabelText('Пароль')).toHaveAttribute('type', 'password');
  });

  it('passes the recipe id from the address to the recipe page', () => {
    const { container } = renderAt('/recipes/42');

    expect(
      screen.getByRole('heading', { level: 1, name: 'Овощная паста с томатами' }),
    ).toBeInTheDocument();
    // The id is bound to the address: the future GET /recipes/{id} will read it here.
    expect(container.querySelector('[data-recipe-id="42"]')).not.toBeNull();
  });

  it('does not render the login form on the recipe page', () => {
    renderAt('/recipes/42');

    expect(screen.queryByLabelText('Email')).not.toBeInTheDocument();
  });

  it('redirects / to the fridge for a signed-in user', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([])));
    renderAt('/');

    expect(await screen.findByRole('heading', { name: 'Мой холодильник' })).toBeInTheDocument();
  });

  it('redirects / to the login page for a guest', () => {
    window.localStorage.clear();
    renderAt('/');

    expect(loginHeading()).toBeInTheDocument();
  });

  it('renders the 404 page for an unknown address', () => {
    renderAt('/no-such-page');

    expect(notFoundHeading()).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Перейти ко входу' })).toHaveAttribute(
      'href',
      '/login',
    );
  });

  it('renders the 404 page when the recipe id is missing', () => {
    renderAt('/recipes/');

    expect(notFoundHeading()).toBeInTheDocument();
  });

  it('navigates from the recipe page to the fridge by the logo', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([])));
    renderAt('/recipes/42');

    await user.click(screen.getByRole('link', { name: 'Recepie Book' }));

    expect(await screen.findByRole('heading', { name: 'Мой холодильник' })).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { level: 1, name: 'Овощная паста с томатами' }),
    ).toBeNull();
  });

  it('keeps the login frame without the navigation', () => {
    renderAt('/login');

    expect(screen.getByRole('link', { name: 'Recepie Book' })).toBeInTheDocument();
    expect(screen.getByText('© 2026 Recepie Book')).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Основная навигация' })).toBeNull();
  });

  it('keeps the signed-in frame with the navigation and the footer', () => {
    renderAt('/recipes/42');

    expect(screen.getByRole('navigation', { name: 'Основная навигация' })).toBeInTheDocument();
    expect(screen.getByText('Меньше лишних покупок. Больше вкусных идей.')).toBeInTheDocument();
  });

  it('logs out from the header and returns to the login screen', async () => {
    const user = userEvent.setup();
    renderAt('/recipes/42');

    await user.click(screen.getByRole('button', { name: 'Выйти' }));

    expect(loginHeading()).toBeInTheDocument();
    expect(window.localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
  });

  it('renders the fridge page for a signed-in user', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([])));
    renderAt('/fridge');

    expect(await screen.findByRole('heading', { name: 'Мой холодильник' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Мой холодильник' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('redirects an unauthenticated visitor to the login screen', () => {
    window.localStorage.clear();
    renderAt('/recipes/42');

    expect(loginHeading()).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { level: 1, name: 'Овощная паста с томатами' }),
    ).toBeNull();
  });
});
