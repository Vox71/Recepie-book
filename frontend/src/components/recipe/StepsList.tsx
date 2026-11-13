import { ArrowUpRight } from 'lucide-react';

import type { RecipeView } from '../../mocks/recipe';
import styles from './StepsList.module.css';

interface StepsListProps {
  recipe: RecipeView;
}

/**
 * "Готовим шаг за шагом": the numbered steps with their time and the source of the idea.
 *
 * The step number is decorative (`aria-hidden`): the `<ol>` already numbers the items for
 * assistive technology, so announcing "1" twice would only be noise.
 */
export default function StepsList({ recipe }: StepsListProps) {
  return (
    <section className={styles.steps} aria-labelledby="steps-heading">
      <header className={styles.header}>
        <h2 id="steps-heading" className={styles.title}>
          Готовим шаг за шагом
        </h2>
        <span className={styles.count}>{recipe.steps.length} простых шага</span>
      </header>

      <ol className={styles.list}>
        {recipe.steps.map((step, index) => (
          <li key={step.title} className={styles.step}>
            <span className={styles.number} aria-hidden="true">
              {index + 1}
            </span>
            <div className={styles.body}>
              <div className={styles.head}>
                <h3 className={styles.stepTitle}>{step.title}</h3>
                <span className={styles.minutes}>{step.minutes} минут</span>
              </div>
              <p className={styles.text}>{step.description}</p>
            </div>
          </li>
        ))}
      </ol>

      <p className={styles.source}>
        <span>Идея рецепта: </span>
        <a
          className={styles.sourceLink}
          href={recipe.source.url}
          target="_blank"
          rel="noreferrer noopener"
        >
          {recipe.source.title}
          <ArrowUpRight size={14} aria-hidden="true" />
        </a>
        <span className={styles.sourceNote}>{recipe.source.note}</span>
      </p>
    </section>
  );
}
