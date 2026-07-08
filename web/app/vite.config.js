import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';

// The bundle is served by the Python panel under /app/ (see pistream_panel.py).
// Hash routing means we never need a server-side SPA fallback, so /app/ as a
// flat static mount is enough — and the exact same build drops into a WebView /
// Capacitor shell later (file:// friendly).
export default defineConfig({
  base: '/app/',
  plugins: [preact()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    assetsDir: 'assets',
    // Stable, unhashed filenames so install.sh can fetch them from GitHub by a
    // fixed path list (the Pi has no Node to build). Cache-busting is handled by
    // the panel serving /app with Cache-Control: no-cache instead.
    rollupOptions: {
      output: {
        entryFileNames: 'assets/index.js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/index.[ext]',
      },
    },
  },
  server: {
    port: 5173,
    // In dev, the Vite server proxies the Python panel's API + shared assets so
    // `npm run dev` talks to a real panel (sandbox on :8787 or the device).
    proxy: {
      '/api': 'http://127.0.0.1:8787',
      '/static': 'http://127.0.0.1:8787',
      '/studio': 'http://127.0.0.1:8787',
    },
  },
});
