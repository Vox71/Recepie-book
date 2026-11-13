import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import App from '../App';

/**
 * Routing tests of the skeleton (sprint 3, task 3).
 *
 * The address is the only input of the application right now, so every case pins one
 * promise of `src/App.tsx`: which page is rendered for a path, that `/` redirects, that an
 * unknown path is a 404 page and that the layout (navigation) is present everywhere.
 * `MemoryRouter` keeps the tests in memory: no jsdom history, no reloads, no network.
 */
function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

const loginHeading = () => screen.getByRole('heading', { name: 'Вход' });

describe('app routing', () => {
  it('renders the login page at /login', () => {
    renderAt('/login');

    expect(loginHeading()).toBeInTheDocument();
    expect(screen.getByLabelText('Электронная почта')).toHaveAttribute('type', 'email');
    expect(screen.getByLabelText('Пароль')).toHaveAttribute('type', 'password');
  });

  it('passes the recipe id from the address to the recipe page', () => {
    renderAt('/recipes/42');

    expect(screen.getByRole('heading', { name: 'Рецепт #42' })).toBeInTheDocument();
  });

  it('does not render the login form on the recipe page', () => {
    renderAt('/recipes/42');

    expect(screen.queryByLabelText('Электронная почта')).not.toBeInTheDocument();
  });

  it('redirects / to the login page', () => {
    renderAt('/');

    expect(loginHeading()).toBeInTheDocument();
  });

  it('renders the 404 page for an unknown address', () => {
    renderAt('/no-such-page');

    expect(screen.getByRole('heading', { name: 'Страница не найдена' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Перейти ко входу' })).toHaveAttribute(
      'href',
      '/login',
    );
  });

  it('renders the 404 page when the recipe id is missing', () => {
    renderAt('/recipes/');

    expect(screen.getByRole('heading', { name: 'Страница не найдена' })).toBeInTheDocument();
  });

  it('navigates from the recipe page to the login page by the link in the layout', async () => {
    const user = userEvent.setup();
    renderAt('/recipes/42');

    await user.click(screen.getByRole('link', { name: 'Вход' }));

    expect(loginHeading()).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Рецепт #42' })).not.toBeInTheDocument();
  });

  it('keeps the layout around every page', () => {
    renderAt('/login');

    expect(screen.getByRole('heading', { level: 1, name: 'Recepie-book' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Основная навигация' })).toBeInTheDocument();
  });
});
