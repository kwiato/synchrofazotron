// Thin wrappers over the panel's JSON API. This is the entire contract between
// the UI and the device — the same module works unchanged when the bundle runs
// in a WebView / Capacitor shell pointed at the Pi.

export async function apiGet(path) {
  const r = await fetch(path, { cache: 'no-store' });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

export async function apiPost(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  try { return await r.json(); } catch { return {}; }
}
