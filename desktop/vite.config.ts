import path from 'node:path';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Relative addresses: the built shell is opened from a file by the desktop app.
  base: './',
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
});
