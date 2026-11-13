import type { InputHTMLAttributes, ReactNode } from 'react';

import styles from './TextField.module.css';

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  id: string;
  /** Optional control inside the field on the right (the password visibility toggle). */
  trailing?: ReactNode;
}

/**
 * Labelled input of the mockups. The label is always a real `<label for="…">`, so clicking
 * the text focuses the field and screen readers announce it; the id is required, because
 * an unbound label is worse than no label at all.
 */
export default function TextField({ label, id, trailing, className, ...rest }: TextFieldProps) {
  const inputClasses = [styles.input, trailing ? styles.withTrailing : '', className]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={id}>
        {label}
      </label>
      <div className={styles.wrapper}>
        <input id={id} className={inputClasses} {...rest} />
        {trailing ? <span className={styles.trailing}>{trailing}</span> : null}
      </div>
    </div>
  );
}
