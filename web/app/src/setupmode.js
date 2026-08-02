// Detection of the device's fallback setup AP (ap-fallback/): the phone joined
// Synchrofazotron-Setup, the panel answers at the fixed AP address. App-build
// only — in the browser the bundle is served by the panel itself, so if you can
// see the page at all, you are already where this would take you.
//
// On detection the app switches itself to the setup device and opens Settings
// (Wi-Fi lives in the default `config` tab); when the AP disappears — the
// device joined a real network — it switches back to the previous device, or
// to the picker when there was none. The previous base rides in sessionStorage
// under the same `prevBase` key the device picker's cancel path uses.
//
// WebView caveat (unlike the native app, which binds its process to the Wi-Fi
// network): with mobile data on, Android may route the probe over cellular and
// never reach 192.168.4.1. It works once the user accepts Android's "this
// network has no internet — stay connected?" prompt, which pins the default
// route to the Wi-Fi.
import { IS_APP, apiBase, setApiBase } from './host.js';

export const SETUP_BASE = 'http://192.168.4.1:8787';

// Session flag: takeover happened for this detection streak. Survives our own
// reload (so we do not re-enter in a loop) and clears when the AP vanishes.
const FLAG = 'setupAuto';

async function probe() {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 2000);
    const r = await fetch(`${SETUP_BASE}/healthz`, { cache: 'no-store', signal: ctrl.signal });
    clearTimeout(t);
    return r.ok && (await r.text()).trim() === 'ok';
  } catch { return false; }
}

export function startSetupWatch() {
  if (!IS_APP) return () => {};
  let stopped = false;
  let misses = 0;

  const tick = async () => {
    if (stopped) return;
    if (await probe()) {
      misses = 0;
      let done = '';
      try { done = sessionStorage.getItem(FLAG) || ''; } catch { /* no storage */ }
      if (apiBase() !== SETUP_BASE && !done) {
        try {
          sessionStorage.setItem(FLAG, '1');
          sessionStorage.setItem('prevBase', apiBase());
          localStorage.setItem('settingstab', 'config'); // the tab with Wi-Fi
        } catch { /* no storage */ }
        setApiBase(SETUP_BASE);
        location.hash = '/settings';
        location.reload();
        return;
      }
    } else {
      try { sessionStorage.removeItem(FLAG); } catch { /* no storage */ }
      // 3 misses ≈ 9 s: don't bounce off one dropped packet while the AP is
      // tearing down/up around a save.
      if (apiBase() === SETUP_BASE && ++misses >= 3) {
        let prev = '';
        try {
          prev = sessionStorage.getItem('prevBase') || '';
          sessionStorage.removeItem('prevBase');
        } catch { /* no storage */ }
        setApiBase(prev);
        location.reload();
        return;
      }
    }
    if (!stopped) setTimeout(tick, 3000);
  };

  tick();
  return () => { stopped = true; };
}
