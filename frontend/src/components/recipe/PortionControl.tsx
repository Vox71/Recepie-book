import styles from './PortionControl.module.css';

interface PortionControlProps {
  servings: string;
  baseServings: string;
  needsBaseServings: boolean;
  error: string | null;
  disabled: boolean;
  onServingsChange: (value: string) => void;
  onBaseServingsChange: (value: string) => void;
}

/**
 * Portions of the recipe.
 *
 * The base value is asked only when the source page did not publish `recipeYield`; the
 * screen never invents it.  The chosen value is local state: the token protects the page,
 * but the arithmetic itself does not belong to the server.
 */
export default function PortionControl({
  servings,
  baseServings,
  needsBaseServings,
  error,
  disabled,
  onServingsChange,
  onBaseServingsChange,
}: PortionControlProps) {
  return (
    <section className={styles.panel} aria-labelledby="portions-heading">
      <div className={styles.heading}>
        <h2 id="portions-heading" className={styles.title}>
          Количество порций
        </h2>
        <span className={styles.note}>
          Числовые количества пересчитываются; «по вкусу» остаётся как в источнике.
        </span>
      </div>

      <div className={styles.fields}>
        {needsBaseServings ? (
          <label className={styles.field}>
            <span>На сколько порций рассчитан рецепт?</span>
            <input
              className={styles.input}
              type="number"
              min={1}
              step={1}
              inputMode="numeric"
              value={baseServings}
              onChange={(event) => onBaseServingsChange(event.target.value)}
            />
          </label>
        ) : null}

        <label className={styles.field}>
          <span>Приготовить порций</span>
          <input
            className={styles.input}
            type="number"
            min={1}
            step={1}
            inputMode="numeric"
            value={servings}
            disabled={disabled}
            onChange={(event) => onServingsChange(event.target.value)}
          />
        </label>
      </div>

      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
      {needsBaseServings && !error ? (
        <p className={styles.hint}>Без базового количества порций пересчёт невозможен.</p>
      ) : null}
    </section>
  );
}
