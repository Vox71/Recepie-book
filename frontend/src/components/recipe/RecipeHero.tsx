import { ChefHat, CircleCheck, Clock, Heart, Users } from 'lucide-react';
import { useState } from 'react';

import recipeHero from '../../assets/recipe-hero.svg';
import type { RecipeView } from '../../mocks/recipe';
import Button from '../ui/Button';
import styles from './RecipeHero.module.css';

interface RecipeHeroProps {
  recipe: RecipeView;
}

/**
 * First screen of the recipe: the photo with its badge, the title, the meta row, the
 * "already in the fridge" banner and the favourite button.
 *
 * The favourite button toggles only the local visual state for now: favourites have their
 * own API (`/favorite_recipes`, sprint 4), and pretending otherwise would be a lie. The
 * button reports the state through `aria-pressed`, so the behaviour is testable.
 */
export default function RecipeHero({ recipe }: RecipeHeroProps) {
  const [favorite, setFavorite] = useState(false);
  const available = recipe.ingredients.filter((item) => item.available).length;

  return (
    <section className={styles.hero} aria-labelledby="recipe-title">
      <div className={styles.media}>
        <img className={styles.image} src={recipeHero} alt={`Фотография блюда «${recipe.title}»`} />
        <span className={styles.badge}>{recipe.badge}</span>
      </div>

      <div className={styles.content}>
        <p className={styles.eyebrow}>{recipe.eyebrow}</p>
        <h1 id="recipe-title" className={styles.title}>
          {recipe.title}
        </h1>
        <p className={styles.description}>{recipe.description}</p>

        <ul className={styles.meta}>
          <li>
            <Clock size={18} aria-hidden="true" />
            {recipe.minutes} минут
          </li>
          <li>
            <ChefHat size={18} aria-hidden="true" />
            {recipe.difficulty}
          </li>
          <li>
            <Users size={18} aria-hidden="true" />
            {recipe.servings} порции
          </li>
        </ul>

        <div className={styles.availability}>
          <span className={styles.availabilityIcon} aria-hidden="true">
            <CircleCheck size={20} />
          </span>
          <div>
            <p className={styles.availabilityTitle}>
              {available} из {recipe.ingredients.length} ингредиентов уже есть
            </p>
            <p className={styles.availabilityText}>Нужно добавить {recipe.missing}</p>
          </div>
        </div>

        <Button
          variant="outline"
          icon={<Heart size={18} />}
          aria-pressed={favorite}
          onClick={() => setFavorite((value) => !value)}
        >
          В избранное
        </Button>
      </div>
    </section>
  );
}
