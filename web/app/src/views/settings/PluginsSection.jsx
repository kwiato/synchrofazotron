import { useEffect, useRef, useState } from 'preact/hooks';
import { useI18n } from '../../i18n.jsx';
import { apiGet, apiPost } from '../../api.js';
import { useApi } from '../../hooks.js';
import { Droplet } from '../../components/Droplet.jsx';
import { usePlugins, pluginApi, pluginT } from '../../plugins.js';

// Settings > Plugins: one card per installed plugin (rendered by the plugin's
// own ui.js → SettingsCard) followed by the management card — installed list
// with remove buttons and an "Install a plugin…" picker fed by the repo
// catalog. Install and remove run on the device as a transient unit that
// restarts the panel at the end, so the card shows a spinner droplet and
// polls until the job is over and the plugin list has changed.
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

const fmt = (s, name) => s.replace('%s', name);

function ManageCard({ installed, dev, onChange }) {
  const { t, lang } = useI18n();
  const [catalog] = useApi('/api/plugins/catalog', 0);
  const [picker, setPicker] = useState(false);
  const [job, setJob] = useState(null);            // {id, name, action} while a job runs
  const [drop, setDrop] = useState(null);          // droplet state: {text, tone, spinner, icon}
  const timer = useRef(null);
  const desc = (r) => (r.description && (r.description[lang] || r.description.en)) || '';

  // Poll the transient unit until it ends; the panel restart in the middle
  // shows up as fetch errors — keep polling through them. Done = the unit is
  // no longer running AND the installed set differs from before (the panel
  // has come back with the new list), or it failed, or 3 minutes passed.
  const watch = (j, before) => {
    setJob(j);
    const started = Date.now();
    clearInterval(timer.current);
    timer.current = setInterval(async () => {
      let st = null;
      try { st = await apiGet('/api/plugins/job'); } catch { /* panel restarting */ }
      const timeout = Date.now() - started > 180000;
      if (st && st.running && !timeout) return;
      let now = before;
      try { now = ((await apiGet('/api/plugins')).plugins || []).map((p) => p.id).join(','); } catch { /* keep */ }
      const failed = !!(st && st.failed);
      if (now === before && !timeout && !failed) return;   // not restarted yet
      clearInterval(timer.current);
      setJob(null);
      const ok = !failed && now !== before;
      const doneKey = j.action === 'install' ? 'plugins_installed_ok' : 'plugins_removed_ok';
      setDrop({ text: ok ? fmt(t(doneKey), j.name) : t('plugins_failed'),
                tone: ok ? 'good' : 'danger', icon: ok ? 'check' : 'x', spinner: false });
      onChange();
    }, 2000);
  };
  useEffect(() => () => clearInterval(timer.current), []);

  const run = async (r, action) => {
    if (action === 'uninstall' && !confirm(t('plugins_remove_confirm'))) return;
    setPicker(false);
    const before = (installed || []).map((p) => p.id).join(',');
    const name = r.name || r.id;
    try {
      const j = await apiPost(`/api/plugins/${action}`, { id: r.id });
      if (!j.ok) { setDrop({ text: j.message || t('js_error'), tone: 'danger', icon: 'x', spinner: false }); return; }
      const key = action === 'install' ? 'plugins_installing' : 'plugins_removing';
      setDrop({ text: fmt(t(key), name), tone: '', spinner: true });
      watch({ id: r.id, name, action }, before);
    } catch { setDrop({ text: t('js_conn_error'), tone: 'danger', icon: 'x', spinner: false }); }
  };

  const have = new Set((installed || []).map((p) => p.id));
  const available = catalog && catalog.ok ? catalog.plugins.filter((c) => !have.has(c.id)) : [];

  return (
    <div class="card">
      <h2><i class="ico ico-puzzle"></i> {t('plugins_head')}</h2>
      <p class="muted">{t('plugins_note')}</p>
      {installed && installed.length === 0 && <p class="muted">{t('plugins_none_installed')}</p>}
      {(installed || []).map((p) => (
        <div class="srow" key={p.id}>
          <div class="info">
            <b>{p.name || p.id}</b>{p.version && <span class="muted small"> v{p.version}</span>}
            {desc(p) && <div class="det">{desc(p)}</div>}
          </div>
          <button class="ebtn" disabled={!!job || dev} title={t('plugins_remove_btn')}
                  aria-label={t('plugins_remove_btn')} onClick={() => run(p, 'uninstall')}>✕</button>
        </div>))}
      <button class="btn" disabled={!!job || dev || !catalog} onClick={() => setPicker(true)}>
        {t('plugins_add_btn')}
      </button>
      {drop && (
        <Droplet inline open text={drop.text} tone={drop.tone} icon={drop.icon}
                 spinner={drop.spinner} timeout={drop.spinner ? 0 : 6000} />
      )}
      {dev && <p class="muted small">{t('plugins_dev')}</p>}

      {picker && (
        <div class="overlay open" onClick={(e) => e.target === e.currentTarget && setPicker(false)}>
          <div class="modal">
            <h2><i class="ico ico-plus"></i> {t('plugins_pick_head')}</h2>
            <p class="muted">{t('plugins_pick_note')}</p>
            {catalog && !catalog.ok && <p class="muted">{t('plugins_catalog_err')}</p>}
            {catalog && catalog.ok && available.length === 0 && (
              <p class="muted">{t(catalog.plugins.length ? 'plugins_all_installed' : 'plugins_none')}</p>)}
            {available.map((c) => (
              <button class="btn sec netbtn" key={c.id} onClick={() => run(c, 'install')}>
                <b>{c.name || c.id}</b>{c.version && <span class="muted small"> v{c.version}</span>}
                {desc(c) && <div class="muted small">{desc(c)}</div>}
              </button>))}
            <button class="btn sec" onClick={() => setPicker(false)}>{t('modal_cancel')}</button>
          </div>
        </div>
      )}
    </div>
  );
}
