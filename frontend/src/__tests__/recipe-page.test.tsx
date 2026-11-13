import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import App from '../App';

/**
 * Recipe screen (sprint 3, task 4): the layout of `frontend/design/02 — Страница
 * рецепта.png`. The data is the typed mock `src/mocks/recipe.ts`, so the cases check the
 * sections of the page and their accessible structure, not a particular pixel.
 */
function renderRecipe(path = '/recipes/42') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe('recipe page', () => {
  it('shows the title, the description and the meta row', () => {
    renderRecipe();

    expect(
      screen.getByRole('heading', { level: 1, name: 'Овощная паста с томатами' }),
    ).toBeInTheDocument();
    expect(screen.getByText('25 минут')).toBeInTheDocument();
    expect(screen.getByText('Легко')).toBeInTheDocument();
    expect(screen.getByText('2 порции')).toBeInTheDocument();
  });

  it('summarises what is already at home and what is missing', () => {
    renderRecipe();

    expect(screen.getByText('5 из 7 ингредиентов уже есть')).toBeInTheDocument();
    expect(screen.getByText('Нужно добавить масло и соль')).toBeInTheDocument();
  });

  it('lists every ingredient with its fridge status and quantity', () => {
    renderRecipe();
    const card = screen.getByRole('complementary', { name: 'Ингредиенты' });
    const items = within(card).getAllByRole('listitem');

    expect(items).toHaveLength(7);
    expect(within(items[0]).getByText('Паста')).toBeInTheDocument();
    expect(within(items[0]).getByText('Есть в холодильнике')).toBeInTheDocument();
    expect(within(items[0]).getByText('200 г')).toBeInTheDocument();
    expect(within(items[5]).getByText('Оливковое масло')).toBeInTheDocument();
    expect(within(items[5]).getByText('Нужно добавить')).toBeInTheDocument();
    expect(within(items[5]).getByText('2 ст. л.')).toBeInTheDocument();
  });

  it('warns about the allergens of the recipe', () => {
    renderRecipe();

    expect(screen.getByText('Аллергены: глютен')).toBeInTheDocument();
  });

  it('renders the steps in order with their time', () => {
    renderRecipe();
    const steps = screen.getByRole('region', { name: 'Готовим шаг за шагом' });
    const items = within(steps).getAllByRole('listitem');

    expect(items).toHaveLength(4);
    expect(
      within(items[0]).getByRole('heading', { level: 3, name: 'Подготовьте овощи' }),
    ).toBeInTheDocument();
    expect(within(items[0]).getByText('5 минут')).toBeInTheDocument();
    expect(
      within(items[3]).getByRole('heading', { level: 3, name: 'Соедините и подавайте' }),
    ).toBeInTheDocument();
    expect(screen.getByText('4 простых шага')).toBeInTheDocument();
  });

  it('links the source of the idea in a new tab safely', () => {
    renderRecipe();
    const link = screen.getByRole('link', { name: 'BBC Good Food' });

    expect(link).toHaveAttribute('href', 'https://www.bbcgoodfood.com/');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link.getAttribute('rel')).toContain('noopener');
    expect(link.getAttribute('rel')).toContain('noreferrer');
  });

  it('toggles the favourite button locally and reports the state', async () => {
    const user = userEvent.setup();
    renderRecipe();
    const favorite = screen.getByRole('button', { name: 'В избранное' });

    expect(favorite).toHaveAttribute('aria-pressed', 'false');

    await user.click(favorite);

    expect(favorite).toHaveAttribute('aria-pressed', 'true');
  });

  it('shows the breadcrumbs with the current recipe', () => {
    renderRecipe();
    const crumbs = screen.getByRole('navigation', { name: 'Хлебные крошки' });

    expect(within(crumbs).getByText('Овощная паста с томатами')).toBeInTheDocument();
    expect(within(crumbs).getByRole('button', { name: 'Лента рецептов' })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
  });

  it('marks the feed as the current section of the navigation', () => {
    renderRecipe();
    const nav = screen.getByRole('navigation', { name: 'Основная навигация' });

    expect(within(nav).getAllByRole('button')).toHaveLength(3);
    expect(within(nav).getByRole('button', { name: 'Лента' })).toHaveAttribute(
      'data-active',
      'true',
    );
    expect(within(nav).getByRole('button', { name: 'Избранное' })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
  });

  it('shows the footer of the signed-in screens', () => {
    renderRecipe();

    expect(screen.getByText('Меньше лишних покупок. Больше вкусных идей.')).toBeInTheDocument();
    expect(screen.getByText('© 2026')).toBeInTheDocument();
  });
});
