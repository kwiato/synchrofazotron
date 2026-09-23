# Synchrofazotron plugins

Optional features that install into the panel without touching its code. A
plugin is one folder, `web/plugins/<id>/`, that the device copies to
`/opt/pistream-panel/plugins/<id>/`. The panel loads every such folder at
boot; the Preact bundle imports the plugin's UI module at runtime. No Node on
the Pi, no rebuild of the panel, no fork of `pistream_panel.py`.

Install / update / remove, on the Pi:

```bash
curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/web/plugins/<id>/install.sh   | sudo bash
curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/web/plugins/<id>/uninstall.sh | sudo bash
```

…or from the panel: **Settings → Plugins** lists this folder's `index.json`
(the catalog) with install / remove buttons. Either way the plugin's script
runs as a transient systemd unit (`synchrofazotron-plugin`) and restarts the
panel at the end.

In a repo checkout the panel (`python web/pistream_panel.py`, sandbox mode)
loads `web/plugins/*` straight from the tree, so a plugin can be developed
with the same edit-and-refresh loop as the rest of the UI (`ui.js` is read
from disk on every request; `plugin.py` needs a panel restart).

## Anatomy

```
web/plugins/<id>/
├── plugin.json    manifest (required)
├── plugin.py      backend (optional — a UI-only plugin can skip it)
├── ui.js          UI module (optional — a headless plugin can skip it)
├── install.sh     copies the folder to /opt/pistream-panel/plugins/<id>
├── uninstall.sh   removes it
└── README.md
```

`<id>`: `a-z`, `0-9`, `-`, starts with a letter, max 32 chars. Must equal
`"id"` in the manifest.

### plugin.json

```json
{
  "id": "pc",
  "name": "PC",
  "version": "0.1.0",
  "description": { "en": "…", "pl": "…" },
  "ui": { "settings": true },
  "i18n": { "en": { "head": "PC", "…": "…" }, "pl": { "head": "PC" } }
}
```

- `ui.settings` — the plugin renders a card in Settings → Plugins (`ui.js`
  exports `SettingsCard`). More placements (a Panel tab) can be added later
  the same way.
- `i18n` — the plugin's own strings, `en` is the fallback. They travel with
  the manifest, so the UI needs no extra request.
- `version` — cache-buster for `ui.js` (bump it when the UI changes).

### plugin.py

```python
def setup(ctx):            # once at boot; ctx is a dict:
    ...                    #   id, dir (plugin folder), data_dir (state folder),
                           #   dev (sandbox mode?), run(cmd) (the panel's _run —
                           #   a no-op in sandbox), lang() (current UI language),
                           #   log(msg)

def handle(method, path, body, query):
    # every /api/p/<id>/<path> request: method "GET"/"POST", path with a
    # leading slash ("/state"), body = parsed JSON (POST), query = dict.
    # Return a JSON-able dict (200), a (status, dict) tuple, or None (404).
    ...
```

Rules of the house:

- **Honour `ctx["dev"]`**: the sandbox never touches the host. Use
  `ctx["run"]` for shell commands (it already does), and check `dev` before
  anything else with side effects (sockets, files outside `data_dir`).
- **State goes to `ctx["data_dir"]`** (`/opt/pistream-panel/plugins-data/<id>/`,
  create it yourself). The plugin folder is replaced on update and deleted on
  uninstall; the data folder survives both.
- **Never raise for user errors** — return `{"ok": False, "message": "…"}`.
  An exception becomes a 500 with the message, and gets logged.
- Stdlib only, like the panel. If the plugin needs a package, `install.sh`
  installs it with `apt-get`.
- The panel runs as root. Validate everything that comes from the request.

### ui.js

A plain ES module. Everything it needs is on `window.sfz`, installed by the
bundle before any plugin is imported:

| Export | What |
|---|---|
| `html` | [htm](https://github.com/developit/htm) bound to Preact: ``html`<div class="card">…` `` |
| `h`, `Fragment`, `hooks` | Preact and `preact/hooks` (`useState`, `useEffect`, …) — the panel's copy; never bundle your own |
| `apiGet(path)`, `apiPost(path, body)`, `apiUrl(path)` | JSON helpers against the current device |
| `useApi(path, intervalMs)` | `[data, reload]` — fetch on mount, optional polling |
| `useI18n()` | `{ t, lang, device, … }` — the panel's strings, not the plugin's |
| `useToast()` | `toast(text)` |
| `Collapsible`, `CardHead`, `EmptyState`, `Tabs`, `Droplet` | shared components |

```js
const { html, hooks: { useState }, useApi, useToast } = window.sfz;

export function SettingsCard({ plugin, t, api }) {
  // plugin — the manifest; t — the plugin's i18n in the panel language;
  // api — { get(p), post(p, body), path(p) } scoped to /api/p/<id>
  const [st, reload] = useApi(api.path('/state'), 5000);
  return html`<div class="card"><h2>${t('head')}</h2>…</div>`;
}
```

Markup: reuse the panel's classes (`card`, `card-head`, `btn`, `btn sec`,
`pill on/off`, `row`, `fieldlabel`, `muted`, `ico ico-*`) so the card is
indistinguishable from a built-in one. The stylesheet is shared; a plugin may
also ship `style.css` next to `ui.js` and inject it itself if it truly needs
something new.

### install.sh / uninstall.sh

Copy `pc/install.sh` — it downloads the plugin's files from GitHub (or uses
the folder it runs from), installs them under `/opt/pistream-panel/plugins/<id>`
and restarts `pistream-panel.service`. Anything system-level the plugin needs
(a package, a kernel overlay, a service) goes here too, idempotently.
`uninstall.sh` undoes it, keeps `plugins-data/<id>` unless `--purge`.

### index.json

The catalog Settings → Plugins shows: `[{id, name, version, description}]`.
Add the new plugin here so it can be installed from the UI.

## Panel side (for reference)

| Method | Path | Description |
|---|---|---|
| GET | `/api/plugins` | installed plugins: manifests + load error, `dev` flag |
| GET | `/api/plugins/catalog` | `index.json` from GitHub (10-minute cache; local file in sandbox) |
| GET | `/api/plugins/job` | `{running, failed}` of the install/remove unit |
| POST | `/api/plugins/install` / `uninstall` | `{"id": "…"}` — runs the plugin's script as a transient unit |
| GET/POST | `/api/p/<id>/…` | forwarded to the plugin's `handle()` |
| GET | `/plugins/<id>/<file>` | `ui.js` and any `.css/.json/.svg` beside it |

Loader: `_plugins_load()` in `pistream_panel.py`, SDK: `web/app/src/plugins.js`,
section: `web/app/src/views/settings/PluginsSection.jsx`.

## Plugins

| id | What |
|---|---|
| [`pc`](pc/) | Wake-on-LAN for a PC on the LAN + up/down check (from [pimote](https://github.com/kwiato/pimote)) |
| [`remote-keyboard`](remote-keyboard/) | USB HID keyboard for the PC: type text, Backspace/Enter, arrows/Esc/Del (from pimote's keyboard half) |
