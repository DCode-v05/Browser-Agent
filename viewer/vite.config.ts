import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  // Relative addresses, so the built viewer works wherever the service mounts it.
  base: './',
  build: {
    // The built viewer ships inside the Python package.
    outDir: '../src/bap_browser/viewer_dist',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
});
