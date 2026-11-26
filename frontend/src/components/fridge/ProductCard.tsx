import { CalendarDays, CircleCheck, Clock3, Trash2, TriangleAlert } from 'lucide-react';

import type { FridgeItem } from '../../api/fridge';
import {
  expirationHint,
  formatExpirationDate,
  getFridgeStatus,
  STATUS_LABELS,
} from './fridgeStatus';
import styles from './ProductCard.module.css';

interface ProductCardProps {
  item: FridgeItem;
  deleting?: boolean;
  onDelete: (item: FridgeItem) => void;
}

const STATUS_ICONS = {
  fresh: CircleCheck,
  soon: Clock3,
  expired: TriangleAlert,
} as const;

/**
 * One product of the fridge: status text, name, quantity and the expiry date.
 *
 * The badge uses both text and an icon, so the status is readable without colour.  The
 * delete button is a real button with an accessible name and is disabled while the
 * request is in flight.
 */
export default function ProductCard({ item, deleting = false, onDelete }: ProductCardProps) {
  const status = getFridgeStatus(item.expiration_date);
  const StatusIcon = STATUS_ICONS[status];

  return (
    <article className={styles.card} data-status={status}>
      <div className={styles.top}>
        <span className={styles.status}>
          <StatusIcon size={16} aria-hidden="true" />
          {STATUS_LABELS[status]}
        </span>
        <button
          type="button"
          className={styles.delete}
          onClick={() => onDelete(item)}
          disabled={deleting}
          aria-label={`Удалить ${item.product_name}`}
          title={`Удалить ${item.product_name}`}
        >
          <Trash2 size={17} aria-hidden="true" />
        </button>
      </div>

      <h3 className={styles.name}>{item.product_name}</h3>
      <p className={styles.quantity}>{item.quantity} шт.</p>

      <p className={styles.date}>
        <CalendarDays size={16} aria-hidden="true" />
        <time dateTime={item.expiration_date}>{formatExpirationDate(item.expiration_date)}</time>
        <span className={styles.hint}>{expirationHint(item.expiration_date)}</span>
      </p>
    </article>
  );
}
