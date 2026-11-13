import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import IngredientsCard from '../components/recipe/IngredientsCard';
import Button from '../components/ui/Button';
import { recipeMock } from '../mocks/recipe';

/**
 * Component-level cases of the design task (sprint 3, task 5: coverage).
 *
 * The page tests already render these components through the pages, so only the branches
 * that the two mockups never reach are checked here: a button without an icon and a recipe
 * without allergens (the peach notice must disappear, not render empty).
 */
describe('ui primitives', () => {
  it('renders a button without an icon', () => {
    render(<Button>Просто кнопка</Button>);

    expect(screen.getByRole('button', { name: 'Просто кнопка' })).toBeInTheDocument();
  });
});

describe('ingredients card', () => {
  it('hides the allergen notice when the recipe has no allergens', () => {
    render(<IngredientsCard recipe={{ ...recipeMock, allergens: [] }} />);

    expect(screen.getByRole('heading', { name: 'Ингредиенты' })).toBeInTheDocument();
    expect(screen.queryByText(/Аллергены/)).not.toBeInTheDocument();
  });
});
