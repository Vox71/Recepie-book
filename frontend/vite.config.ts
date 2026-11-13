import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

/**
 * The dev server listens on 3000 on purpose: that is the origin in `CORS_ORIGINS`
 * (`.env.example`, `docker-compose.yml`), so Vite must not silently move to 3001 -
 * every API call of the future tasks would then be blocked by CORS (`strictPort`).
 *
 * Tests run under jsdom with the same config: no second toolchain, no extra config file.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true,
    host: true,
  },
  preview: {
    port: 3000,
    strictPort: true,
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    /**
     * Coverage of the client (sprint 3, task 5). The report is measured over the sources of
     * the application; the bootstrap, the test setup, the mock data and the assets are
     * excluded on purpose, and docs/test-coverage.md explains every exclusion. The same
     * threshold is enforced in Frontend CI, so a drop fails the build instead of being
     * noticed later.
     */
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary', 'html'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/main.tsx', // bootstrap: mounts the app, like backend main.py/worker.py
        'src/vite-env.d.ts', // ambient types, no code
        'src/test/**', // test harness
        'src/mocks/**', // fixture data, not logic
        'src/assets/**', // assets, not code
        'src/**/*.test.{ts,tsx}',
      ],
      thresholds: {
        statements: 80,
        branches: 80,
        functions: 80,
        lines: 80,
      },
    },
  },
});
