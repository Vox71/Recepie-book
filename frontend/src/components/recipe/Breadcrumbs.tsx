import { ArrowLeft } from 'lucide-react';

import styles from './Breadcrumbs.module.css';

interface BreadcrumbsProps {
  title: string;
}

/**
 * "← Лента рецептов / <title>" above the hero.
 *
 * The feed page does not exist yet, so the back control is a button marked
 * `aria-disabled` rather than a link to nowhere; the current recipe is plain text.
 */
export default function Breadcrumbs({ title }: BreadcrumbsProps) {
  return (
    <nav className={styles.nav} aria-label="Хлебные крошки">
      <button
        type="button"
        className={styles.back}
        aria-disabled="true"
        title="Лента рецептов появится позже"
      >
        <ArrowLeft size={18} aria-hidden="true" />
        Лента рецептов
      </button>
      <span className={styles.separator} aria-hidden="true">
        /
      </span>
      <span className={styles.current} aria-current="page">
        {title}
      </span>
    </nav>
  );
}
