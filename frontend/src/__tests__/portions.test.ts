import { describe, expect, it } from 'vitest';

import { scaleNutrition, scaleQuantity } from '../components/recipe/portions';
import type { RecipeNutritionDto } from '../api/recipes';

const NUTRITION: RecipeNutritionDto = {
  calories_total: 500,
  protein_total: 20,
  fat_total: 10,
  carbs_total: 60,
  calories_per_100g: 100,
  protein_per_100g: 4,
  fat_per_100g: 2,
  carbs_per_100g: 12,
  source: 'povarenok',
};

describe('scaleQuantity', () => {
  it('scales grams and converts kilograms to grams', () => {
    expect(scaleQuantity('200 г', 1.5)).toBe('300 г');
    expect(scaleQuantity('1 кг', 1.5)).toBe('1500 г');
    expect(scaleQuantity('0,5 кг', 2)).toBe('1000 г');
  });

  it('keeps countable and volume units', () => {
    expect(scaleQuantity('2 шт.', 1.5)).toBe('3 шт.');
    expect(scaleQuantity('1,5 ст. л.', 2)).toBe('3 ст. л.');
    expect(scaleQuantity('200 мл', 2)).toBe('400 мл');
  });

  it('scales a range at both ends', () => {
    expect(scaleQuantity('1–2 шт.', 2)).toBe('2–4 шт.');
  });

  it('does not invent a number for an amount without one', () => {
    expect(scaleQuantity('по вкусу', 2)).toBe('по вкусу');
    expect(scaleQuantity(null, 2)).toBe('—');
  });

  it('returns the source text for an invalid factor', () => {
    expect(scaleQuantity('200 г', 0)).toBe('200 г');
  });
});

describe('scaleNutrition', () => {
  it('scales totals and derives values per serving', () => {
    expect(scaleNutrition(NUTRITION, 2, 4)).toEqual({
      caloriesTotal: 1000,
      proteinTotal: 40,
      fatTotal: 20,
      carbsTotal: 120,
      caloriesPer100g: 100,
      proteinPer100g: 4,
      fatPer100g: 2,
      carbsPer100g: 12,
      caloriesPerServing: 250,
      proteinPerServing: 10,
      fatPerServing: 5,
      carbsPerServing: 30,
    });
  });

  it('returns null when the recipe has no nutrition', () => {
    expect(scaleNutrition(null, 2, 4)).toBeNull();
  });
});
