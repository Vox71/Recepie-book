import { CircleCheck, CircleDashed, CirclePlus } from 'lucide-react';

import type { RecipeView } from './types';
import styles from './IngredientsCard.module.css';

interface IngredientsCardProps {
  recipe: RecipeView;
}

function servingsLabel(servings: number | null): string {
  if (servings === null) {
    return 'Порции не указаны';
  }
  const word = servings === 1 ? 'порцию' : servings < 5 ? 'порции' : 'порций';
  return `На ${servings} ${word}`;
}

/**
 * Ingredients with the fridge status and the amount already scaled to the chosen
 * servings. The status is written as text, so it stays readable without colour; `null`
 * means the fridge request failed and the page must not claim that a product is missing.
 */
export default function IngredientsCard({ recipe }: IngredientsCardProps) {
  return (
    <aside className={styles.card} aria-labelledby="ingredients-heading">
      <header className={styles.header}>
        <h2 id="ingredients-heading" className={styles.title}>
          Ингредиенты
        </h2>
        <span className={styles.servings}>{servingsLabel(recipe.servings)}</span>
      </header>

      <ul className={styles.list}>
        {recipe.ingredients.map((item) => (
          <li key={item.name} className={styles.item}>
            <span
              className={styles.status}
              data-available={item.available === null ? 'unknown' : String(item.available)}
              aria-hidden="true"
            >
              {item.available === true ? (
                <CircleCheck size={20} />
              ) : item.available === false ? (
                <CirclePlus size={20} />
              ) : (
                <CircleDashed size={20} />
              )}
            </span>
            <span className={styles.name}>
              {item.name}
              <span className={styles.hint}>
                {item.available === true
                  ? 'Есть в холодильнике'
                  : item.available === false
                    ? 'Нужно добавить'
                    : 'Статус неизвестен'}
              </span>
            </span>
            <span className={styles.quantity}>{item.quantity}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
