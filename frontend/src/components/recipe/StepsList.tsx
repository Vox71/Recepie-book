import { ArrowUpRight } from 'lucide-react';

import type { RecipeStepView } from './types';
import styles from './StepsList.module.css';

interface StepsListProps {
  steps: RecipeStepView[];
  sourceUrl: string | null;
  sourceLabel: string;
}

function stepsLabel(count: number): string {
  if (count === 1) {
    return '1 шаг';
  }
  if (count < 5) {
    return `${count} шага`;
  }
  return `${count} шагов`;
}

/**
 * "Готовим шаг за шагом": the steps from `recipe_steps` and the source link.
 *
 * `recipe_steps` has no per-step duration, so the screen does not invent one. The source
 * is shown only when the recipe has a URL; a manual recipe is not given a fake link.
 */
export default function StepsList({ steps, sourceUrl, sourceLabel }: StepsListProps) {
  return (
    <section className={styles.steps} aria-labelledby="steps-heading">
      <header className={styles.header}>
        <h2 id="steps-heading" className={styles.title}>
          Готовим шаг за шагом
        </h2>
        <span className={styles.count}>{stepsLabel(steps.length)}</span>
      </header>

      {steps.length === 0 ? (
        <p className={styles.text}>Шаги приготовления не указаны.</p>
      ) : (
        <ol className={styles.list}>
          {steps.map((step) => (
            <li key={step.number} className={styles.step}>
              <span className={styles.number} aria-hidden="true">
                {step.number}
              </span>
              <div className={styles.body}>
                <div className={styles.head}>
                  <h3 className={styles.stepTitle}>Шаг {step.number}</h3>
                </div>
                <p className={styles.text}>{step.text}</p>
              </div>
            </li>
          ))}
        </ol>
      )}

      {sourceUrl ? (
        <p className={styles.source}>
          <span>Источник рецепта: </span>
          <a
            className={styles.sourceLink}
            href={sourceUrl}
            target="_blank"
            rel="noreferrer noopener"
          >
            {sourceLabel}
            <ArrowUpRight size={14} aria-hidden="true" />
          </a>
        </p>
      ) : (
        <p className={styles.source}>Источник не указан.</p>
      )}
    </section>
  );
}
