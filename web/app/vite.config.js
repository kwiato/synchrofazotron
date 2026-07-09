import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';

// Two build targets from one source:
//   * default  -> served by the Python panel under /app/ (base '/app/', outDir
//     'dist', committed to the repo for install.sh — the Pi has no Node).
//   * mode 'capacitor' (`vite build --mode capacitor`) -> the Android/WebView
//     shell. Served from the app root, so base is relative ('./') and it lands
//     in its own 'dist-cap' (gitignored) that Capacitor syncs into the APK.
//     `.env.capacitor` sets VITE_CAPACITOR=1 so the bundle can self-host its
//     CSS instead of linking the panel's /static/style.css (see main.jsx).
// Hash routing means neither target needs a server-side SPA fallback.
export default defineConfig(({ mode }) => {
  const cap = mode === 'capacitor';
  return {
  base: cap ? './' : '/app/',
  plugins: [preact()],
  build: {
    outDir: cap ? 'dist-cap' : 'dist',
    emptyOutDir: true,
    assetsDir: 'assets',
    // Stable, unhashed filenames so install.sh can fetch them from GitHub by a
    // fixed path list (the Pi has no Node to build). Cache-busting is handled by
    // the panel serving /app with Cache-Control: no-cache instead.
    rollupOptions: {
      output: {
        // One JS chunk: keeps the Pi's shipped file list a fixed { index.js,
        // index.css } (install.sh fetches by exact path) and folds in Capacitor
        // plugins' lazily-imported web stubs instead of emitting stray chunks.
        inlineDynamicImports: true,
        entryFileNames: 'assets/index.js',
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
  };
});
