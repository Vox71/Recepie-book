/** One ingredient as the page renders it: the amount is already scaled to the chosen servings. */
export interface RecipeIngredientView {
  name: string;
  quantity: string;
  /** `null` means the fridge is unavailable, not that the product is missing. */
  available: boolean | null;
}

/** One step of the recipe; the API has text and an optional photo, but no per-step timer. */
export interface RecipeStepView {
  number: number;
  text: string;
  imageUrl: string | null;
}

/** The subset of `Recipe` that the screen needs. */
export interface RecipeView {
  id: number;
  title: string;
  minutes: number | null;
  difficulty: string | null;
  servings: number | null;
  ingredients: RecipeIngredientView[];
  steps: RecipeStepView[];
  sourceUrl: string | null;
  sourceLabel: string;
}
