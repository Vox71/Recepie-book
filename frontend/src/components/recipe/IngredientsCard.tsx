import { CircleCheck, CirclePlus, Wheat } from 'lucide-react';

import type { RecipeView } from '../../mocks/recipe';
import styles from './IngredientsCard.module.css';

interface IngredientsCardProps {
  recipe: RecipeView;
}

/**
 * Ingredients of the recipe with the fridge status of every item (mockup 02).
 *
 * The status is written as text ("Есть в холодильнике" / "Нужно добавить") and the icon
 * only repeats it, so the list stays readable without colour and for a screen reader.
 */
export default function IngredientsCard({ recipe }: IngredientsCardProps) {
  return (
    <aside className={styles.card} aria-labelledby="ingredients-heading">
      <header className={styles.header}>
        <h2 id="ingredients-heading" className={styles.title}>
          Ингредиенты
        </h2>
        <span className={styles.servings}>На {recipe.servings} порции</span>
      </header>

      <ul className={styles.list}>
        {recipe.ingredients.map((item) => (
          <li key={item.name} className={styles.item}>
            <span
              className={styles.status}
              data-available={item.available ? 'true' : 'false'}
              aria-hidden="true"
            >
              {item.available ? <CircleCheck size={20} /> : <CirclePlus size={20} />}
            </span>
            <span className={styles.name}>
              {item.name}
              <span className={styles.hint}>
                {item.available ? 'Есть в холодильнике' : 'Нужно добавить'}
              </span>
            </span>
            <span className={styles.quantity}>{item.quantity}</span>
          </li>
        ))}
      </ul>

      {recipe.allergens.length > 0 ? (
        <p className={styles.allergens}>
          <Wheat size={18} aria-hidden="true" />
          Аллергены: {recipe.allergens.join(', ')}
        </p>
      ) : null}
    </aside>
  );
}
