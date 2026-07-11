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

// Devices the app has successfully talked to, most recent first — the picker
// lists them so switching devices (or reconnecting away from home, where mDNS
// cannot see anything) is one tap. Capped small; url is the dedupe key.
const KNOWN_KEY = 'knownDevices';

export function knownDevices() {
  try { return JSON.parse(localStorage.getItem(KNOWN_KEY)) || []; } catch { return []; }
}

export function rememberDevice(name, url) {
  const list = [{ name, url }, ...knownDevices().filter((d) => d.url !== url)].slice(0, 6);
  try { localStorage.setItem(KNOWN_KEY, JSON.stringify(list)); } catch { /* no storage */ }
}

export function forgetDevice(url) {
  const list = knownDevices().filter((d) => d.url !== url);
  try { localStorage.setItem(KNOWN_KEY, JSON.stringify(list)); } catch { /* no storage */ }
}

// LMS artwork/icons live on the LMS web port (9000), which the phone often
// cannot reach (bound locally / cleartext-blocked / not on the tailnet). Route
// them through the panel's own origin instead — it proxies to LMS on localhost.
export function lmsArt(path) {
  return apiUrl('/api/lms/art?path=' + encodeURIComponent(path));
}

// Resolve an LMS icon path (relative or absolute) to a panel-proxied URL.
export function lmsIcon(icon) {
  return icon ? lmsArt(icon) : '';
}

// Drop the current device and reload — sends the app back to the picker. The
// previous base is stashed for the session so the picker can offer "cancel"
// (restore it) instead of "skip"; a successful pick discards the stash.
export function switchDevice() {
  try { sessionStorage.setItem('prevBase', base); } catch { /* no storage */ }
  setApiBase('');
  location.reload();
}

export function prevBase() {
  try { return sessionStorage.getItem('prevBase') || ''; } catch { return ''; }
}

export function clearPrevBase() {
  try { sessionStorage.removeItem('prevBase'); } catch { /* no storage */ }
}
