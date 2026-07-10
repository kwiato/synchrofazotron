// Direct TuneIn browsing for the app shell: the phone talks to TuneIn's OPML
// API itself and only sends "play this URL" / favorites to the device. This
// keeps the Pi out of the browse path entirely — faster lists, icons straight
// from the CDN, zero LMS load (browsing through LMS once memory-starved the
// Pi). Uses CapacitorHttp (native) because the OPML API sends no CORS headers,
// so a WebView fetch() would be blocked. The web build keeps the LMS path.
import { CapacitorHttp } from '@capacitor/core';

const BROWSE = 'https://opml.radiotime.com/Browse.ashx';
const SEARCH = 'https://opml.radiotime.com/Search.ashx';

const withJson = (u) =>
  u.includes('render=json') ? u : u + (u.includes('?') ? '&' : '?') + 'render=json';

// TuneIn outlines -> the app's normalized list items. Grouped results
// ("Stations" / "Shows") flatten into header rows + their children.
function norm(outlines) {
  const items = [];
  for (const o of outlines || []) {
    if (o.children) {
      if (o.text) items.push({ header: true, title: o.text });
      items.push(...norm(o.children));
      continue;
    }
    if (o.element !== 'outline' || !o.URL) continue;
    const audio = o.type === 'audio';
    if (!audio && o.type !== 'link') continue;
    items.push({
      title: o.text || '',
      icon: o.image || '',
      playable: audio,
      browsable: !audio,
      url: o.URL,
      fav: audio ? { url: o.URL, title: o.text || '', icon: o.image || '' } : null,
    });
  }
  return items;
}

// Short-lived cache so back-navigation is instant and TuneIn is not hammered.
const cache = new Map();   // url -> {t, items}
const TTL = 10 * 60 * 1000;

async function get(url) {
  const hit = cache.get(url);
  if (hit && Date.now() - hit.t < TTL) return hit.items;
  const r = await CapacitorHttp.get({ url, headers: { Accept: 'application/json' } });
  if (r.status !== 200) throw new Error('HTTP ' + r.status);
  const body = typeof r.data === 'string' ? JSON.parse(r.data) : r.data;
  const items = norm(body && body.body);
  cache.set(url, { t: Date.now(), items });
  return items;
}

export const tuneinRoot = () => get(withJson(BROWSE));
export const tuneinBrowse = (url) => get(withJson(url));
export const tuneinSearch = (q) => get(withJson(SEARCH) + '&query=' + encodeURIComponent(q));
