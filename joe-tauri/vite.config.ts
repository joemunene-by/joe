import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

/**
 * Multi-page Vite build:
 *   - index.html: the menu-bar fallback (static "start joe-http" page,
 *                 preserved from v0.2 unchanged).
 *   - desktop.html: the React-based full desktop app, mounted by
 *                   the Tauri webview window labeled "desktop".
 *
 * Outputs to ../dist/, which is what tauri.conf.json's frontendDist points at.
 */
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        index: resolve(__dirname, 'index.html'),
        desktop: resolve(__dirname, 'desktop.html'),
      },
    },
  },
  server: {
    port: 5174,
    strictPort: true,
  },
  clearScreen: false,
});
