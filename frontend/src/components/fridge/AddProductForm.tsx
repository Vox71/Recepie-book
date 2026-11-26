import { Plus } from 'lucide-react';
import { useState } from 'react';
import type { FormEvent } from 'react';

import { ApiError } from '../../api/client';
import { addFridgeItem } from '../../api/fridge';
import Button from '../ui/Button';
import TextField from '../ui/TextField';
import styles from './AddProductForm.module.css';

interface AddProductFormProps {
  token: string;
  onSaved: () => void;
  onCancel: () => void;
  onUnauthorized: () => void;
}

function today(): string {
  const date = new Date();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

/** Inline form of `POST /profile/fridge`; the owner comes from the token, not from a field. */
export default function AddProductForm({
  token,
  onSaved,
  onCancel,
  onUnauthorized,
}: AddProductFormProps) {
  const [name, setName] = useState('');
  const [quantity, setQuantity] = useState('1');
  const [expirationDate, setExpirationDate] = useState(today());
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await addFridgeItem(token, {
        product_name: name,
        expiration_date: expirationDate,
        quantity: Number(quantity),
      });
      onSaved();
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        onUnauthorized();
        return;
      }
      setError(cause instanceof Error ? cause.message : 'Не удалось добавить продукт');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className={styles.form} onSubmit={handleSubmit} aria-label="Добавить продукт">
      <h2 className={styles.title}>Новый продукт</h2>
      <div className={styles.fields}>
        <TextField
          id="fridge-product-name"
          name="product_name"
          label="Название продукта"
          placeholder="Например, молоко"
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={100}
          required
        />
        <TextField
          id="fridge-quantity"
          name="quantity"
          label="Количество"
          type="number"
          min={1}
          step={1}
          value={quantity}
          onChange={(event) => setQuantity(event.target.value)}
          required
        />
        <TextField
          id="fridge-expiration-date"
          name="expiration_date"
          label="Срок годности"
          type="date"
          value={expirationDate}
          onChange={(event) => setExpirationDate(event.target.value)}
          required
        />
      </div>
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
      <div className={styles.actions}>
        <Button type="submit" icon={<Plus size={18} />} disabled={saving}>
          {saving ? 'Добавляем…' : 'Добавить'}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel} disabled={saving}>
          Отмена
        </Button>
      </div>
    </form>
  );
}
