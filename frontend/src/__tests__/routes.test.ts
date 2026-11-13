import { describe, expect, it } from 'vitest';

import { recipePath } from '../app/routes';

/**
 * The routes table (sprint 3, task 5: coverage of the client).
 *
 * `recipePath` is the only place that turns a recipe id into an address, so it deserves its
 * own cases: a plain number, a numeric string and an id that needs escaping.
 */
describe('routes table', () => {
  it('builds a concrete recipe address from an id', () => {
    expect(recipePath(42)).toBe('/recipes/42');
    expect(recipePath('42')).toBe('/recipes/42');
  });

  it('escapes an id that is not a plain number', () => {
    expect(recipePath('a/b c')).toBe('/recipes/a%2Fb%20c');
  });
});
