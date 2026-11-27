import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

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

/** Component-level branches that the page scenarios do not reach. */
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
