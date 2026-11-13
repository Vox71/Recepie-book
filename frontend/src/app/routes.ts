/**
 * Every address of the application lives here.
 *
 * Pages never spell a URL out as a string: they take it from this table or build it with
 * `recipePath()`. When a path changes (or a page is added), the compiler points at every
 * `<Link>` that used the old value, and the routing tests keep the table honest.
 */
export const ROUTES = {
  home: '/',
  login: '/login',
  recipe: '/recipes/:recipeId',
  notFound: '*',
} as const;

/** A path of the table, including the parameterized ones (`/recipes/:recipeId`). */
export type RoutePath = (typeof ROUTES)[keyof typeof ROUTES];

/** Build a concrete recipe address (`/recipes/42`); the argument is escaped. */
export function recipePath(recipeId: string | number): string {
  return `/recipes/${encodeURIComponent(String(recipeId))}`;
}
