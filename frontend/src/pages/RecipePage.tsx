import { useParams } from 'react-router-dom';

/**
 * Recipe screen skeleton.
 *
 * The address carries the id (`/recipes/42`), so the page already knows which recipe the
 * user opened. The recipe itself, its steps and the timers arrive in the next frontend
 * tasks (`GET /recipes/{id}`, then `/timers`): there is no data loading here on purpose.
 */
export default function RecipePage() {
  const { recipeId } = useParams<{ recipeId: string }>();

  return (
    <section>
      <h2>Рецепт #{recipeId}</h2>
      <p>Карточка рецепта, шаги и таймеры появятся в следующих задачах.</p>
    </section>
  );
}
