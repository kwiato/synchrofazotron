// Which device the app talks to.
//
// In the browser / Pi build the bundle is served *by* the panel, so the base is
// empty and every path stays same-origin and relative ('/api/...') — unchanged
// behaviour. In the Capacitor shell the bundle is loaded from the app itself
// (capacitor://localhost), so there is no panel to be same-origin with: the user
// picks a device on the LAN and we remember its base URL (http://<ip>:8787).
// apiUrl() is the single choke point that turns a panel path into a real URL, so
// switching devices is just changing this one value.

// True only in the Android/WebView build (set by .env.capacitor). Gates the
// device-picker: on the web there is nothing to pick, base is always same-origin.
export const IS_APP = import.meta.env.VITE_CAPACITOR === '1';

const KEY = 'apiBase';
let base = '';
try { base = localStorage.getItem(KEY) || ''; } catch { /* no storage */ }

export function apiBase() { return base; }

// Empty string clears the selection (back to the device picker in the app).
export function setApiBase(v) {
  base = (v || '').replace(/\/+$/, '');
  try {
    if (base) localStorage.setItem(KEY, base);
    else localStorage.removeItem(KEY);
  } catch { /* no storage */ }
}

// A panel path ('/api/...', '/healthz', '/static/...') -> absolute URL against
// the chosen device, or left relative when there is no base (web build).
export function apiUrl(path) {
  return base ? base + path : path;
}

// Drop the current device and reload — sends the app back to the picker.
export function switchDevice() {
  setApiBase('');
  location.reload();
}
