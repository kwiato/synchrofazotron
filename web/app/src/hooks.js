import { useCallback, useEffect, useRef, useState } from 'preact/hooks';
import { apiGet, apiPost } from './api.js';
import { apiUrl } from './host.js';

// Lightweight touch-swipe detector. Spread the returned handlers onto an element
// ({...useSwipe({ onLeft, onRight, onUp, onDown })}); the matching callback fires
// on a deliberate flick. Axis dominance (1.4×) + a distance threshold keep it
// from stealing vertical scrolls or firing on taps. We never preventDefault, so
// native scrolling and clicks still work.
export function useSwipe({ onLeft, onRight, onUp, onDown, threshold = 50 } = {}) {
  const start = useRef(null);
  const onTouchStart = (e) => {
    const t = e.touches[0];
    start.current = t ? { x: t.clientX, y: t.clientY, at: Date.now() } : null;
  };
  const onTouchEnd = (e) => {
    const s = start.current;
    start.current = null;
    const t = e.changedTouches[0];
    if (!s || !t || Date.now() - s.at > 700) return;   // stale or too slow to be a flick
    const dx = t.clientX - s.x, dy = t.clientY - s.y;
    const ax = Math.abs(dx), ay = Math.abs(dy);
    const fire = (fn) => { if (fn) fn(); };
    if (ax > ay * 1.4 && ax > threshold) fire(dx < 0 ? onLeft : onRight);
    else if (ay > ax * 1.4 && ay > threshold) fire(dy < 0 ? onUp : onDown);
  };
  return { onTouchStart, onTouchEnd };
}

// Fetch a JSON endpoint on mount and (optionally) on an interval. Returns the
// last payload plus a manual reload(). Last value is kept on error, matching the
// old panel's "don't blank the UI on a hiccup" behaviour.
export function useApi(path, interval) {
  const [data, setData] = useState(null);
  const reload = useCallback(async () => {
    try { setData(await apiGet(path)); } catch { /* keep last */ }
  }, [path]);
  useEffect(() => {
    reload();
    if (!interval) return undefined;
    const id = setInterval(reload, interval);
    return () => clearInterval(id);
  }, [reload, interval]);
  return [data, reload];
}

// Per-source volume (0-100). Fetches /api/volume (only sources controllable
// right now appear), and setVolume() updates the UI immediately while trailing-
// throttling the POST so dragging a slider doesn't flood the player APIs.
export function useVolumes() {
  const [volumes, setVolumes] = useState({});
  const timers = useRef({});
  const reload = useCallback(async () => {
    try { setVolumes((await apiGet('/api/volume')).volumes || {}); } catch { /* keep */ }
  }, []);
  useEffect(() => { reload(); }, [reload]);
  const setVolume = useCallback((source, value) => {
    const v = Math.max(0, Math.min(100, Math.round(value)));
    setVolumes((cur) => ({ ...cur, [source]: v }));
    clearTimeout(timers.current[source]);
    timers.current[source] = setTimeout(() => {
      apiPost('/api/volume', { source, value: v }).catch(() => {});
    }, 120);
  }, []);
  useEffect(() => () => Object.values(timers.current).forEach(clearTimeout), []);
  return { volumes, setVolume, reload };
}

// Polls /healthz until the device goes down and comes back (reboot / update),
// then fires done(). Falls through after ~4 min so spinners never hang.
export function watchComeBack(done) {
  let wentDown = false;
  const started = Date.now();
  const iv = setInterval(async () => {
    try {
      const r = await fetch(apiUrl('/healthz'), { cache: 'no-store' });
      if (r.ok && wentDown) { clearInterval(iv); done(); return; }
    } catch { wentDown = true; }        // unreachable -> restarting
    if (Date.now() - started > 240000) { clearInterval(iv); done(); }
  }, 3000);
}

// Shared reboot flow (used by the reboot card and the audio card's reboot
// button): confirm, POST, then wait for the device to return.
export async function doReboot({ t, toast, onStart, onDone }) {
  if (!confirm(t('js_reboot_confirm'))) return;
  if (onStart) onStart();
  try { await apiPost('/api/reboot'); } catch { /* it is going down anyway */ }
  watchComeBack(() => {
    if (onDone) onDone();
    if (toast) toast(t('reboot_done_toast'));
    setTimeout(() => location.reload(), 1800);
  });
}
