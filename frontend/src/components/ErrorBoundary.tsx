import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

import styles from './ErrorBoundary.module.css';

interface ErrorBoundaryState {
  failed: boolean;
}

interface ErrorBoundaryProps {
  children: ReactNode;
}

/**
 * Last line of defence against a blank page.
 *
 * React unmounts the whole tree when a render throws. Without this boundary the user
 * would see an empty document; here they get a readable message and a reload action.
 * Event-handler and async errors still have to be handled by the page that owns them.
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Keep the diagnostic in the browser console; the user gets a short message.
    console.error('Unhandled UI error', error, info.componentStack);
  }

  render() {
    if (this.state.failed) {
      return (
        <main className={styles.page} role="alert">
          <h1 className={styles.title}>Что-то пошло не так</h1>
          <p className={styles.text}>
            Страница не загрузилась. Попробуйте обновить её — данные и вход сохранены.
          </p>
          <button type="button" className={styles.button} onClick={() => window.location.reload()}>
            Обновить страницу
          </button>
        </main>
      );
    }
    return this.props.children;
  }
}
