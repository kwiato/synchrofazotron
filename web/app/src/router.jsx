import { useEffect, useState } from 'preact/hooks';

// Hash routing: /app/#/settings. No server-side SPA fallback needed anywhere —
// works the same served from the Pi, in Vite dev, and in a file:// WebView. The
// route set is tiny and closed, so a hand-rolled hook beats pulling in a router.

export function currentPath() {
  const h = location.hash.replace(/^#/, '');
  return h || '/';
}

export function navigate(path) {
  location.hash = path;
}

export function useRoute() {
  const [path, setPath] = useState(currentPath());
  useEffect(() => {
    const on = () => setPath(currentPath());
    addEventListener('hashchange', on);
    return () => removeEventListener('hashchange', on);
  }, []);
  return path;
}
