import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

/**
 * Runs before every test file (see `vite.config.ts`).
 *
 * `@testing-library/jest-dom/vitest` adds the DOM matchers (`toBeInTheDocument`, ...),
 * and the cleanup is explicit because the tests import `it/expect` from `vitest` instead
 * of enabling globals: without it the DOM of one test would leak into the next one.
 */
afterEach(() => {
  cleanup();
});
