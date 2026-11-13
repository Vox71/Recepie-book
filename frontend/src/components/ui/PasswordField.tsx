import { Eye, EyeOff } from 'lucide-react';
import { useState } from 'react';
import type { InputHTMLAttributes } from 'react';

import TextField from './TextField';
import styles from './PasswordField.module.css';

type PasswordFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & {
  label: string;
  id: string;
};

/**
 * Password input with the visibility toggle of the mockup.
 *
 * The toggle is a real button: it is reachable by keyboard, reports its state through
 * `aria-pressed`, and its accessible name changes ("Показать пароль" / "Скрыть пароль").
 * Showing the password never copies it anywhere - only the input type changes.
 */
export default function PasswordField({ label, id, ...rest }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);

  return (
    <TextField
      label={label}
      id={id}
      type={visible ? 'text' : 'password'}
      trailing={
        <button
          type="button"
          className={styles.toggle}
          onClick={() => setVisible((value) => !value)}
          aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'}
          aria-pressed={visible}
          title={visible ? 'Скрыть пароль' : 'Показать пароль'}
        >
          {visible ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
        </button>
      }
      {...rest}
    />
  );
}
