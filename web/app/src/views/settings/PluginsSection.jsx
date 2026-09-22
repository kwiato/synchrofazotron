import { useEffect, useRef, useState } from 'preact/hooks';
import { useI18n } from '../../i18n.jsx';
import { apiGet, apiPost } from '../../api.js';
import { useApi } from '../../hooks.js';
import { useToast } from '../../components/Toast.jsx';
import { usePlugins, pluginApi, pluginT } from '../../plugins.js';

// Settings > Plugins: one card per installed plugin (rendered by the plugin's
// own ui.js → SettingsCard) followed by the management card — the repo
// catalog with install / remove buttons. Install and remove run on the device
// as a transient unit that restarts the panel at the end, so the section just
// polls until the job is over and the plugin list changes.
export function PluginsSection() {
  const { t, lang } = useI18n();
  const [data, reload] = usePlugins();
  return (
    <section class="active">
      <div class="sect-title">{t('nav_plugins')}</div>
      <div class="cardgrid">
        {data && data.plugins.map((p) => <PluginCard key={p.id} plugin={p} lang={lang} />)}
        <ManageCard installed={data ? data.plugins : null} dev={!!(data && data.dev)}
                    onChange={reload} />
      </div>
    </section>
  );
}

function PluginCard({ plugin, lang }) {
  const { t } = useI18n();
  const Card = plugin.mod && plugin.mod.SettingsCard;
  if (Card && !plugin.error) {
    return <Card plugin={plugin} t={pluginT(plugin, lang)} api={pluginApi(plugin.id)} />;
  }
  if (!plugin.error && !plugin.has_ui) return null;    // headless plugin — nothing to show
  return (
    <div class="card">
      <h2>{plugin.name}</h2>
      <p class="muted">{plugin.error ? t('plugins_broken') : t('plugins_ui_err')}</p>
      {(plugin.error || plugin.uiError) && <p class="muted small"><code>{plugin.error || plugin.uiError}</code></p>}
    </div>
  );
}

function ManageCard({ installed, dev, onChange }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const [catalog] = useApi('/api/plugins/catalog', 0);
  const [job, setJob] = useState(null);            // id of the plugin being worked on
  const [failed, setFailed] = useState(false);
  const timer = useRef(null);

  // Poll the transient unit until it ends; the panel restart in the middle
  // shows up as fetch errors — keep polling through them.
  const watch = (id, before) => {
    setJob(id);
    setFailed(false);
    const started = Date.now();
    clearInterval(timer.current);
    timer.current = setInterval(async () => {
      let st = null;
      try { st = await apiGet('/api/plugins/job'); } catch { /* panel restarting */ }
      const timeout = Date.now() - started > 180000;
      if (st && st.running && !timeout) return;
      if (st && st.failed) setFailed(true);
      let now = before;
      try { now = ((await apiGet('/api/plugins')).plugins || []).map((p) => p.id).join(','); } catch { /* keep */ }
      if (now === before && !timeout && !(st && st.failed)) return;   // not restarted yet
      clearInterval(timer.current);
      setJob(null);
      onChange();
    }, 2000);
  };
  useEffect(() => () => clearInterval(timer.current), []);

  const run = async (id, action) => {
    if (action === 'uninstall' && !confirm(t('plugins_remove_confirm'))) return;
    const before = (installed || []).map((p) => p.id).join(',');
    try {
      const j = await apiPost(`/api/plugins/${action}`, { id });
      toast(j.message || (j.ok ? '' : t('js_error')));
      if (j.ok) watch(id, before);
    } catch { toast(t('js_conn_error')); }
  };

  const have = new Map((installed || []).map((p) => [p.id, p]));
  // Catalog first (it carries descriptions), then anything installed that the
  // catalog does not list (a local / hand-copied plugin).
  const rows = [];
  if (catalog && catalog.ok) for (const c of catalog.plugins) rows.push({ ...c, ...(have.get(c.id) || {}), listed: true });
  for (const p of have.values()) if (!rows.some((r) => r.id === p.id)) rows.push({ ...p, listed: false });
  const desc = (r) => (r.description && (r.description[lang] || r.description.en)) || '';

  return (
    <div class="card">
      <h2><i class="ico ico-puzzle"></i> {t('plugins_head')}</h2>
      <p class="muted">{t('plugins_note')}</p>
      {catalog && !catalog.ok && <p class="muted">{t('plugins_catalog_err')}</p>}
      {catalog && catalog.ok && rows.length === 0 && <p class="muted">{t('plugins_none')}</p>}
      {rows.map((r) => {
        const on = have.has(r.id);
        const busy = job === r.id;
        return (
          <div class="row" key={r.id}>
            <div class="info">
              <b>{r.name || r.id}</b>{r.version && <span class="muted small"> v{r.version}</span>}
              {desc(r) && <div class="muted small">{desc(r)}</div>}
            </div>
            <span class={'pill ' + (on ? 'on' : 'off')}>{t(on ? 'plugins_installed' : 'plugins_available')}</span>
            {(r.listed || on) && (
              <button class="ebtn" disabled={!!job || dev} title={t(on ? 'plugins_remove_btn' : 'plugins_install_btn')}
                      onClick={() => run(r.id, on ? 'uninstall' : 'install')}>
                {busy ? '…' : on ? '✕' : '+'}
              </button>)}
          </div>);
      })}
      {job && <p class="muted">{t('plugins_working')}</p>}
      {failed && <p class="muted">{t('plugins_failed')}</p>}
      {dev && <p class="muted small">{t('plugins_dev')}</p>}
    </div>
  );
}
