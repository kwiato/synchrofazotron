import { h, Fragment } from 'preact';
import * as hooks from 'preact/hooks';
import htm from 'htm';
import { apiGet, apiPost } from './api.js';
import { apiUrl } from './host.js';
import { useApi } from './hooks.js';
import { useI18n } from './i18n.jsx';
import { useToast } from './components/Toast.jsx';
import { Collapsible } from './components/Collapsible.jsx';
import { CardHead } from './components/CardHead.jsx';
import { EmptyState } from './components/EmptyState.jsx';
import { Tabs } from './components/Tabs.jsx';
import { Droplet } from './components/Droplet.jsx';

// Plugins: optional features the device installs into plugins/<id>/ next to
// the panel (see web/plugins/README.md). The bundle is prebuilt and the Pi has
// no Node, so a plugin's UI cannot be compiled in — instead each plugin ships a
// plain ES module (ui.js) that the SPA imports at runtime from the device, and
// this file hands it everything it needs through window.sfz: Preact itself
// (one copy — a plugin bundling its own would break hooks), htm so it can write
// html`<div class="card">…` without a build step, the JSON API helpers and the
// shared components, so a plugin card looks exactly like a built-in one.

export const html = htm.bind(h);

// Backend calls scoped to one plugin: /api/p/<id>/<path>.
function pluginApi(id) {
  const path = (p) => `/api/p/${id}${p}`;
  return {
    path,
    get: (p) => apiGet(path(p)),
    post: (p, body) => apiPost(path(p), body),
  };
}

// Plugin strings come with the manifest (plugin.json → i18n{en,pl}) and
// follow the panel's language, with en filling any holes.
function pluginT(manifest, lang) {
  const i18n = manifest.i18n || {};
  const cur = i18n[lang] || {};
  const en = i18n.en || {};
  return (key) => cur[key] ?? en[key] ?? key;
}

// Version-stamped so an updated plugin is not served from the browser cache.
const modCache = new Map();          // id@version -> Promise<module>
function loadModule(m) {
  const key = `${m.id}@${m.version}`;
  if (!modCache.has(key)) {
    const url = apiUrl(`/plugins/${m.id}/ui.js?v=${encodeURIComponent(m.version)}`);
    modCache.set(key, import(/* @vite-ignore */ url));
  }
  return modCache.get(key);
}

// Installed plugins with their UI modules resolved: [{ ...manifest, mod,
// uiError }]. Polled slowly so a freshly installed plugin shows up after the
// panel restart without a page reload.
export function usePlugins(interval = 15000) {
  const [list, reload] = useApi('/api/plugins', interval);
  const [ready, setReady] = hooks.useState(null);
  hooks.useEffect(() => {
    if (!list) return;
    let alive = true;
    Promise.all((list.plugins || []).map(async (m) => {
      if (m.error || !m.has_ui) return { ...m, mod: null, uiError: '' };
      try { return { ...m, mod: await loadModule(m), uiError: '' }; }
      catch (e) { return { ...m, mod: null, uiError: String(e && e.message || e) }; }
    })).then((r) => { if (alive) setReady({ plugins: r, dev: !!list.dev }); });
    return () => { alive = false; };
  }, [list]);
  return [ready, reload];
}

// Everything a plugin's ui.js may use. Frozen once at boot; a plugin reads it
// as `const { html, hooks: { useState }, useToast } = window.sfz;`.
export function installSdk() {
  if (window.sfz) return;
  window.sfz = Object.freeze({
    h, Fragment, html, hooks,
    apiGet, apiPost, apiUrl, useApi, useI18n, useToast,
    Collapsible, CardHead, EmptyState, Tabs, Droplet,
    pluginApi, pluginT,
  });
}

export { pluginApi, pluginT };
