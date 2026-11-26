import { Leaf, Plus, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { ApiError } from '../api/client';
import { deleteExpiredFridgeItems, deleteFridgeItem, listFridgeItems } from '../api/fridge';
import type { FridgeItem } from '../api/fridge';
import { useAuth } from '../auth/AuthContext';
import AddProductForm from '../components/fridge/AddProductForm';
import FridgeSummary from '../components/fridge/FridgeSummary';
import ProductCard from '../components/fridge/ProductCard';
import { daysUntil, expirationHint, getFridgeStatus } from '../components/fridge/fridgeStatus';
import type { FridgeStatus } from '../components/fridge/fridgeStatus';
import Button from '../components/ui/Button';
import styles from './FridgePage.module.css';

type FridgeFilter = 'all' | 'soon' | 'expired';

const FILTERS: ReadonlyArray<{ id: FridgeFilter; label: string }> = [
  { id: 'all', label: 'Все' },
  { id: 'soon', label: 'Скоро истекают' },
  { id: 'expired', label: 'Просроченные' },
];

interface FridgeItemWithStatus extends FridgeItem {
  status: FridgeStatus;
}

/**
 * Fridge screen: the owner comes from the JWT, so the page always shows the products of
 * the signed-in user. Add, delete and "remove expired" call the protected
 * `/profile/fridge` endpoints; filters and the summary are calculated on the client.
 */
export default function FridgePage() {
  const { token, logout } = useAuth();
  const [items, setItems] = useState<FridgeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FridgeFilter>('all');
  const [showForm, setShowForm] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [removingExpired, setRemovingExpired] = useState(false);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (!token) {
        return;
      }
      setLoading(true);
      setError(null);
      try {
        setItems(await listFridgeItems(token, signal));
      } catch (cause) {
        if (signal?.aborted) {
          return;
        }
        if (cause instanceof ApiError && cause.status === 401) {
          logout();
          return;
        }
        setError(cause instanceof Error ? cause.message : 'Не удалось загрузить холодильник');
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [logout, token],
  );

  useEffect(() => {
    const controller = new AbortController();
    // Defer the first request one tick: the effect must not call setState synchronously
    // (react-hooks/set-state-in-effect), and the abort still cancels a request on unmount.
    const timer = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load]);

  const itemsWithStatus = useMemo<FridgeItemWithStatus[]>(
    () =>
      items.map((item) => ({
        ...item,
        status: getFridgeStatus(item.expiration_date),
      })),
    [items],
  );

  const counts = useMemo(() => {
    const soon = itemsWithStatus.filter((item) => item.status === 'soon').length;
    const expired = itemsWithStatus.filter((item) => item.status === 'expired').length;
    return { total: itemsWithStatus.length, soon, expired };
  }, [itemsWithStatus]);

  const soonItems = useMemo(
    () =>
      itemsWithStatus
        .filter((item) => item.status === 'soon')
        .sort((left, right) => daysUntil(left.expiration_date) - daysUntil(right.expiration_date)),
    [itemsWithStatus],
  );

  const visibleItems = useMemo(
    () =>
      filter === 'all' ? itemsWithStatus : itemsWithStatus.filter((item) => item.status === filter),
    [filter, itemsWithStatus],
  );

  const handleDelete = async (item: FridgeItem) => {
    if (!token) {
      return;
    }
    setDeletingId(item.id);
    setError(null);
    try {
      await deleteFridgeItem(token, item.id);
      setItems((current) => current.filter((row) => row.id !== item.id));
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        logout();
        return;
      }
      setError(cause instanceof Error ? cause.message : 'Не удалось удалить продукт');
    } finally {
      setDeletingId(null);
    }
  };

  const handleRemoveExpired = async () => {
    if (!token) {
      return;
    }
    setRemovingExpired(true);
    setError(null);
    try {
      await deleteExpiredFridgeItems(token);
      await load();
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        logout();
        return;
      }
      setError(cause instanceof Error ? cause.message : 'Не удалось удалить просроченные');
    } finally {
      setRemovingExpired(false);
    }
  };

  if (!token) {
    return null;
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <p className={styles.eyebrow}>Продукты дома</p>
          <h1 className={styles.title}>Мой холодильник</h1>
          <p className={styles.subtitle}>Следите за сроками и готовьте из того, что уже есть.</p>
        </div>
        <div className={styles.actions}>
          <Button
            type="button"
            icon={<Plus size={18} />}
            onClick={() => setShowForm((value) => !value)}
          >
            Добавить продукт
          </Button>
          <Button
            type="button"
            variant="outline"
            icon={<Trash2 size={18} />}
            onClick={handleRemoveExpired}
            disabled={counts.expired === 0 || removingExpired}
            title="Удалить просроченные продукты"
          >
            {removingExpired ? 'Удаляем…' : 'Удалить просроченные'}
          </Button>
        </div>
      </header>

      {showForm ? (
        <div className={styles.formWrap}>
          <AddProductForm
            token={token}
            onSaved={() => {
              setShowForm(false);
              void load();
            }}
            onCancel={() => setShowForm(false)}
            onUnauthorized={logout}
          />
        </div>
      ) : null}

      <FridgeSummary total={counts.total} soon={counts.soon} expired={counts.expired} />

      {error ? (
        <div className={styles.error} role="alert">
          <span>{error}</span>
          <button type="button" className={styles.retry} onClick={() => void load()}>
            Повторить
          </button>
        </div>
      ) : null}

      <div className={styles.content}>
        <section className={styles.main} aria-labelledby="fridge-products-heading">
          <div className={styles.sectionHeader}>
            <h2 id="fridge-products-heading" className={styles.sectionTitle}>
              Продукты
            </h2>
            <div className={styles.filters} role="group" aria-label="Фильтр продуктов">
              {FILTERS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  className={styles.filter}
                  aria-pressed={filter === id}
                  onClick={() => setFilter(id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {loading && items.length === 0 ? (
            <p className={styles.state} role="status">
              Загружаем холодильник…
            </p>
          ) : visibleItems.length === 0 ? (
            <p className={styles.state} role="status">
              {items.length === 0
                ? 'В холодильнике пока пусто. Добавьте первый продукт.'
                : 'По этому фильтру продуктов нет.'}
            </p>
          ) : (
            <ul className={styles.grid}>
              {visibleItems.map((item) => (
                <li key={item.id} className={styles.gridItem}>
                  <ProductCard
                    item={item}
                    deleting={deletingId === item.id}
                    onDelete={handleDelete}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside className={styles.aside} aria-label="Советы по холодильнику">
          <section className={styles.panel} aria-labelledby="use-first-heading">
            <h2 id="use-first-heading" className={styles.panelTitle}>
              Сначала используйте
            </h2>
            {soonItems.length === 0 ? (
              <p className={styles.panelText}>Скоро истекающих продуктов нет.</p>
            ) : (
              <ul className={styles.soonList}>
                {soonItems.slice(0, 4).map((item) => (
                  <li key={item.id} className={styles.soonItem}>
                    <span>{item.product_name}</span>
                    <span className={styles.soonHint}>{expirationHint(item.expiration_date)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className={styles.tip} aria-labelledby="fridge-tip-heading">
            <Leaf size={20} aria-hidden="true" />
            <h2 id="fridge-tip-heading" className={styles.panelTitle}>
              Маленький совет
            </h2>
            <p className={styles.panelText}>
              Сначала готовьте то, что истекает раньше, — так продукты не придётся выбрасывать.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
