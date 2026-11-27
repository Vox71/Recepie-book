import { apiRequest } from './client';

/** `RecipeIngredient` of openapi.yaml: one row of `recipe_ingredients`. */
export interface RecipeIngredientDto {
  name: string;
  quantity: string | null;
}

/** `RecipeStep` of openapi.yaml. */
export interface RecipeStepDto {
  number: number;
  text: string;
  image_url: string | null;
}

/** `RecipeNutrition` of openapi.yaml; every value is optional in the source page. */
export interface RecipeNutritionDto {
  calories_total: number | null;
  protein_total: number | null;
  fat_total: number | null;
  carbs_total: number | null;
  calories_per_100g: number | null;
  protein_per_100g: number | null;
  fat_per_100g: number | null;
  carbs_per_100g: number | null;
  source: string | null;
}

/** `Recipe` of openapi.yaml. */
export interface RecipeDto {
  id: number;
  name: string;
  ingredients: string;
  ingredient_list: RecipeIngredientDto[];
  instructions: string | null;
  difficulty_level: string | null;
  source_url: string | null;
  cooking_time_minutes: number | null;
  servings: number | null;
  steps: RecipeStepDto[];
  nutrition: RecipeNutritionDto | null;
}

/** `GET /recipes/{id}`: the card of one recipe. */
export function getRecipe(
  token: string,
  recipeId: string,
  signal?: AbortSignal,
): Promise<RecipeDto> {
  return apiRequest<RecipeDto>(`/recipes/${encodeURIComponent(recipeId)}`, { token, signal });
}
