import { ChefHat, CircleCheck, Clock, Heart, Users } from 'lucide-react';
import { useState } from 'react';

import recipeHero from '../../assets/recipe-hero.svg';
import type { RecipeView } from './types';
import Button from '../ui/Button';
import styles from './RecipeHero.module.css';

interface RecipeHeroProps {
  recipe: RecipeView;
}

/**
 * First screen of the recipe: the photo, title, meta row, fridge summary and favourite
 * button. The recipe comes from `GET /recipes/{id}`; the only local state is the visual
 * state of the favourite button, because favourites still have no client API call.
 */
export default function RecipeHero({ recipe }: RecipeHeroProps) {
  const [favorite, setFavorite] = useState(false);
  const known =
    recipe.ingredients.length > 0 && recipe.ingredients.every((item) => item.available !== null);
  const available = recipe.ingredients.filter((item) => item.available === true).length;
  const missing = recipe.ingredients
    .filter((item) => item.available === false)
    .map((item) => item.name);

  return (
    <section className={styles.hero} aria-labelledby="recipe-title">
      <div className={styles.media}>
        <img className={styles.image} src={recipeHero} alt={`Фотография блюда «${recipe.title}»`} />
      </div>

      <div className={styles.content}>
        <p className={styles.eyebrow}>Рецепт</p>
        <h1 id="recipe-title" className={styles.title}>
          {recipe.title}
        </h1>

        <ul className={styles.meta}>
          <li>
            <Clock size={18} aria-hidden="true" />
            {recipe.minutes === null ? 'Время не указано' : `${recipe.minutes} минут`}
          </li>
          <li>
            <ChefHat size={18} aria-hidden="true" />
            {recipe.difficulty ?? 'Сложность не указана'}
          </li>
          <li>
            <Users size={18} aria-hidden="true" />
            {recipe.servings === null ? 'Порции не указаны' : `${recipe.servings} порции`}
          </li>
        </ul>

        <div className={styles.availability}>
          <span className={styles.availabilityIcon} aria-hidden="true">
            <CircleCheck size={20} />
          </span>
          {known ? (
            <div>
              <p className={styles.availabilityTitle}>
                {available} из {recipe.ingredients.length} ингредиентов уже есть
              </p>
              <p className={styles.availabilityText}>
                {missing.length === 0
                  ? 'Все ингредиенты есть в холодильнике'
                  : `Нужно добавить: ${missing.join(', ')}`}
              </p>
            </div>
          ) : (
            <div>
              <p className={styles.availabilityTitle}>Состав холодильника недоступен</p>
              <p className={styles.availabilityText}>
                Ингредиенты показаны без отметок «есть / нужно добавить».
              </p>
            </div>
          )}
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
