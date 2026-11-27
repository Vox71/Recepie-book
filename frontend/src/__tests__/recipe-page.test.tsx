import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { RecipeDto } from '../api/recipes';
import App from '../App';
import { TOKEN_STORAGE_KEY } from '../auth/AuthContext';

const RECIPE: RecipeDto = {
  id: 42,
  name: 'Овощная паста с томатами',
  ingredients: 'Паста, томаты, оливковое масло, соль',
  ingredient_list: [
    { name: 'Паста', quantity: '200 г' },
    { name: 'Томаты', quantity: '4 шт.' },
    { name: 'Оливковое масло', quantity: '2 ст. л.' },
    { name: 'Соль', quantity: 'по вкусу' },
  ],
  instructions: '1. Подготовьте овощи',
  difficulty_level: 'Легко',
  source_url: 'https://www.povarenok.ru/recipes/show/42/',
  cooking_time_minutes: 25,
  servings: 2,
  steps: [
    { number: 1, text: 'Подготовьте овощи', image_url: null },
    { number: 2, text: 'Отварите пасту', image_url: null },
  ],
  nutrition: {
    calories_total: 500,
    protein_total: 20,
    fat_total: 10,
    carbs_total: 60,
    calories_per_100g: 100,
    protein_per_100g: 4,
    fat_per_100g: 2,
    carbs_per_100g: 12,
    source: 'povarenok',
  },
};

const FRIDGE = [
  {
    id: 1,
    user_id: 1,
    product_name: 'Паста',
    expiration_date: '2026-12-01',
    quantity: 1,
    last_added: '2026-11-25T10:00:00+00:00',
  },
  {
    id: 2,
    user_id: 1,
    product_name: 'Томаты',
    expiration_date: '2026-12-01',
    quantity: 4,
    last_added: '2026-11-25T10:00:00+00:00',
  },
];

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

function renderRecipe(path = '/recipes/42') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

function mockFetch(recipe: RecipeDto = RECIPE, fridge: unknown[] = FRIDGE) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/recipes/42')) {
      return jsonResponse(recipe);
    }
    if (url.includes('/profile/fridge')) {
      return jsonResponse(fridge);
    }
    return jsonResponse({ error: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

beforeEach(() => {
  window.localStorage.setItem(TOKEN_STORAGE_KEY, 'test-token');
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('recipe page', () => {
  it('loads the recipe from the API and shows its meta row', async () => {
    mockFetch();
    renderRecipe();

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Овощная паста с томатами' }),
    ).toBeInTheDocument();
    expect(screen.getByText('25 минут')).toBeInTheDocument();
    expect(screen.getByText('Легко')).toBeInTheDocument();
    expect(screen.getByText('2 порции')).toBeInTheDocument();
  });

  it('summarises the fridge and lists the scaled ingredients', async () => {
    mockFetch();
    renderRecipe();

    expect(await screen.findByText('2 из 4 ингредиентов уже есть')).toBeInTheDocument();
    expect(screen.getByText('Нужно добавить: Оливковое масло, Соль')).toBeInTheDocument();

    const card = screen.getByRole('complementary', { name: 'Ингредиенты' });
    expect(within(card).getAllByText('Есть в холодильнике')).toHaveLength(2);
    expect(within(card).getByText('200 г')).toBeInTheDocument();
    expect(within(card).getByText('4 шт.')).toBeInTheDocument();
    expect(within(card).getByText('по вкусу')).toBeInTheDocument();
  });

  it('recalculates ingredients and nutrition when the servings change', async () => {
    const user = userEvent.setup();
    mockFetch();
    renderRecipe();

    const servingInput = await screen.findByLabelText('Приготовить порций');
    await user.clear(servingInput);
    await user.type(servingInput, '4');

    const card = screen.getByRole('complementary', { name: 'Ингредиенты' });
    expect(within(card).getByText('400 г')).toBeInTheDocument();
    expect(within(card).getByText('8 шт.')).toBeInTheDocument();
    expect(within(card).getByText('4 ст. л.')).toBeInTheDocument();
    expect(within(card).getByText('по вкусу')).toBeInTheDocument();

    const nutrition = screen.getByRole('region', { name: 'Пищевая ценность' });
    expect(within(nutrition).getByText('1000 ккал')).toBeInTheDocument();
    expect(within(nutrition).getByText('250 ккал')).toBeInTheDocument();
  });

  it('asks for the base servings when the recipe does not declare them', async () => {
    const user = userEvent.setup();
    mockFetch({ ...RECIPE, servings: null });
    renderRecipe();

    expect(await screen.findByLabelText('На сколько порций рассчитан рецепт?')).toBeInTheDocument();
    expect(screen.getByLabelText('Приготовить порций')).toBeDisabled();

    await user.type(screen.getByLabelText('На сколько порций рассчитан рецепт?'), '2');
    expect(screen.getByLabelText('Приготовить порций')).toBeEnabled();
    await user.clear(screen.getByLabelText('Приготовить порций'));
    await user.type(screen.getByLabelText('Приготовить порций'), '4');

    const card = screen.getByRole('complementary', { name: 'Ингредиенты' });
    expect(within(card).getByText('400 г')).toBeInTheDocument();
  });

  it('keeps the previous amounts and reports an invalid serving count', async () => {
    const user = userEvent.setup();
    mockFetch();
    renderRecipe();

    const servingInput = await screen.findByLabelText('Приготовить порций');
    await user.clear(servingInput);
    await user.type(servingInput, '0');

    expect(screen.getByRole('alert')).toHaveTextContent('Введите целое положительное число порций');
    const card = screen.getByRole('complementary', { name: 'Ингредиенты' });
    expect(within(card).getByText('200 г')).toBeInTheDocument();
  });

  it('shows the steps and the source of the recipe', async () => {
    mockFetch();
    renderRecipe();

    const steps = await screen.findByRole('region', { name: 'Готовим шаг за шагом' });
    expect(within(steps).getAllByRole('listitem')).toHaveLength(2);
    expect(within(steps).getByRole('heading', { name: 'Шаг 1' })).toBeInTheDocument();
    expect(within(steps).getByText('Отварите пасту')).toBeInTheDocument();
    expect(within(steps).getByRole('link', { name: 'povarenok.ru' })).toHaveAttribute(
      'href',
      'https://www.povarenok.ru/recipes/show/42/',
    );
  });

  it('shows a readable 404 error and retries', async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ error: 'Recipe not found' }, 404)),
    );
    renderRecipe();

    expect(await screen.findByRole('alert')).toHaveTextContent('Рецепт не найден');
    await user.click(screen.getByRole('button', { name: 'Повторить' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Рецепт не найден');
  });

  it('keeps the ingredients visible when the fridge request fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        return url.includes('/recipes/42')
          ? jsonResponse(RECIPE)
          : jsonResponse({ error: 'Fridge is down' }, 500);
      }),
    );
    renderRecipe();

    expect(await screen.findByText('Не удалось получить состав холодильника.')).toBeInTheDocument();
    expect(screen.getAllByText('Статус неизвестен')).toHaveLength(4);
  });
});
