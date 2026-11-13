import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import App from '../App';

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

  it('redirects / to the login page', () => {
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

  it('navigates from the recipe page to the login page by the logo', async () => {
    const user = userEvent.setup();
    renderAt('/recipes/42');

    await user.click(screen.getByRole('link', { name: 'Recepie Book' }));

    expect(loginHeading()).toBeInTheDocument();
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
});
