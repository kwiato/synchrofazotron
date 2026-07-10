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

// "Homepage" gesture (the logo, the player bar): land on / with the Now tab
// active. The tab lives in Panel's state + localStorage, so navigate() alone
// wouldn't switch it — the event tells a mounted Panel to flip.
export function goHome() {
  try { localStorage.setItem('paneltab', 'now'); } catch { /* private mode */ }
  navigate('/');
  dispatchEvent(new Event('app:home'));
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
