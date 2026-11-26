import { Clock3, Package, TriangleAlert } from 'lucide-react';

import styles from './FridgeSummary.module.css';

interface FridgeSummaryProps {
  total: number;
  soon: number;
  expired: number;
}

/**
 * Three counters above the product list. The numbers are plain text, so the same
 * information is available to a screen reader and without colour.
 */
export default function FridgeSummary({ total, soon, expired }: FridgeSummaryProps) {
  const cards = [
    { label: 'Всего продуктов', value: total, tone: 'neutral', icon: Package },
    { label: 'Скоро истекают', value: soon, tone: 'soon', icon: Clock3 },
    { label: 'Просрочено', value: expired, tone: 'expired', icon: TriangleAlert },
  ] as const;

  return (
    <section className={styles.summary} aria-label="Сводка по холодильнику">
      {cards.map(({ label, value, tone, icon: Icon }) => (
        <article key={label} className={styles.card} data-tone={tone}>
          <span className={styles.icon} aria-hidden="true">
            <Icon size={20} />
          </span>
          <span className={styles.value}>{value}</span>
          <span className={styles.label}>{label}</span>
        </article>
      ))}
    </section>
  );
}
