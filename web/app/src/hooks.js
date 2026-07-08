import { useCallback, useEffect, useState } from 'preact/hooks';
import { apiGet, apiPost } from './api.js';

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

// Polls /healthz until the device goes down and comes back (reboot / update),
// then fires done(). Falls through after ~4 min so spinners never hang.
export function watchComeBack(done) {
  let wentDown = false;
  const started = Date.now();
  const iv = setInterval(async () => {
    try {
      const r = await fetch('/healthz', { cache: 'no-store' });
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
