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
  },
});
