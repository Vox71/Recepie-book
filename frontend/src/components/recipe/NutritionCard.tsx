import type { ScaledNutrition } from './portions';
import { formatNutritionValue } from './portions';
import styles from './NutritionCard.module.css';

interface NutritionCardProps {
  nutrition: ScaledNutrition | null;
  source: string | null;
  servings: number;
}

/** Nutrition of the whole dish, one chosen serving and 100 g. */
export default function NutritionCard({ nutrition, source, servings }: NutritionCardProps) {
  return (
    <section className={styles.card} aria-labelledby="nutrition-heading">
      <header className={styles.header}>
        <h2 id="nutrition-heading" className={styles.title}>
          Пищевая ценность
        </h2>
        <span className={styles.servings}>На {servings} порции</span>
      </header>

      {nutrition === null ? (
        <p className={styles.empty}>Для этого рецепта нет данных о калорийности и БЖУ.</p>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <caption className={styles.caption}>
              Значения пересчитаны для выбранного количества порций
            </caption>
            <thead>
              <tr>
                <th scope="col">Показатель</th>
                <th scope="col">На всё блюдо</th>
                <th scope="col">На порцию</th>
                <th scope="col">На 100 г</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Калорийность</th>
                <td>{formatNutritionValue(nutrition.caloriesTotal, 'ккал')}</td>
                <td>{formatNutritionValue(nutrition.caloriesPerServing, 'ккал')}</td>
                <td>{formatNutritionValue(nutrition.caloriesPer100g, 'ккал')}</td>
              </tr>
              <tr>
                <th scope="row">Белки</th>
                <td>{formatNutritionValue(nutrition.proteinTotal, 'г')}</td>
                <td>{formatNutritionValue(nutrition.proteinPerServing, 'г')}</td>
                <td>{formatNutritionValue(nutrition.proteinPer100g, 'г')}</td>
              </tr>
              <tr>
                <th scope="row">Жиры</th>
                <td>{formatNutritionValue(nutrition.fatTotal, 'г')}</td>
                <td>{formatNutritionValue(nutrition.fatPerServing, 'г')}</td>
                <td>{formatNutritionValue(nutrition.fatPer100g, 'г')}</td>
              </tr>
              <tr>
                <th scope="row">Углеводы</th>
                <td>{formatNutritionValue(nutrition.carbsTotal, 'г')}</td>
                <td>{formatNutritionValue(nutrition.carbsPerServing, 'г')}</td>
                <td>{formatNutritionValue(nutrition.carbsPer100g, 'г')}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {source ? <p className={styles.source}>Источник данных: {source}</p> : null}
    </section>
  );
}
