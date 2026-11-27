import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import ErrorBoundary from '../components/ErrorBoundary';
import IngredientsCard from '../components/recipe/IngredientsCard';
import type { RecipeView } from '../components/recipe/types';
import Button from '../components/ui/Button';

const RECIPE: RecipeView = {
  id: 1,
  title: 'Тестовый рецепт',
  minutes: null,
  difficulty: null,
  servings: 2,
  ingredients: [
    { name: 'Соль', quantity: 'по вкусу', available: null },
    { name: 'Молоко', quantity: '200 мл', available: true },
  ],
  steps: [],
  sourceUrl: null,
  sourceLabel: '',
};

afterEach(() => {
  vi.restoreAllMocks();
});

/** Component-level branches that the page scenarios do not reach. */
describe('error boundary', () => {
  it('shows a readable fallback instead of a blank page', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    function Broken(): never {
      throw new Error('render failed');
    }

    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Что-то пошло не так');
    expect(screen.getByRole('button', { name: 'Обновить страницу' })).toBeInTheDocument();
  });
});

describe('ui primitives', () => {
  it('renders a button without an icon', () => {
    render(<Button>Просто кнопка</Button>);

    expect(screen.getByRole('button', { name: 'Просто кнопка' })).toBeInTheDocument();
  });
});

describe('ingredients card', () => {
  it('shows an unknown fridge status without claiming the product is missing', () => {
    render(<IngredientsCard recipe={RECIPE} />);

    expect(screen.getByRole('heading', { name: 'Ингредиенты' })).toBeInTheDocument();
    expect(screen.getByText('Статус неизвестен')).toBeInTheDocument();
    expect(screen.queryByText('Нужно добавить')).not.toBeInTheDocument();
  });
});
