import { useParams } from 'react-router-dom';

import Breadcrumbs from '../components/recipe/Breadcrumbs';
import IngredientsCard from '../components/recipe/IngredientsCard';
import RecipeHero from '../components/recipe/RecipeHero';
import StepsList from '../components/recipe/StepsList';
import { recipeMock } from '../mocks/recipe';
import styles from './RecipePage.module.css';

/**
 * Recipe screen of the mockup `frontend/design/02 — Страница рецепта.png` (task 4).
 *
 * The data is a typed mock: `GET /recipes/{id}` and the real steps/nutrition land in
 * sprint 4, and the mock repeats the shapes of the contract, so the markup survives that
 * switch. The id from the address is kept on the container, so the page is already bound
 * to `/recipes/:recipeId` and the future request.
 */
export default function RecipePage() {
  const { recipeId } = useParams<{ recipeId: string }>();
  const recipe = recipeMock;

  return (
    <div className={styles.page} data-recipe-id={recipeId}>
      <Breadcrumbs title={recipe.title} />
      <RecipeHero recipe={recipe} />
      <div className={styles.content}>
        <IngredientsCard recipe={recipe} />
        <StepsList recipe={recipe} />
      </div>
    </div>
  );
}
