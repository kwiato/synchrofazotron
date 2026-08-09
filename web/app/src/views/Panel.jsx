import { useEffect, useState } from 'preact/hooks';
import { useSwipe } from '../hooks.js';
import { useStatus } from '../status.jsx';
import { useI18n } from '../i18n.jsx';
import { apiGet, apiPost } from '../api.js';
import { lmsArt } from '../host.js';
import { primary, srcSub } from '../util.js';
import { Eq } from '../components/Eq.jsx';
import { Collapsible } from '../components/Collapsible.jsx';
import { Tabs } from '../components/Tabs.jsx';
import { EmptyState } from '../components/EmptyState.jsx';
import { RadioTab } from './Radio.jsx';
import { TidalTab } from './Tidal.jsx';

// Main view: the Now / Radio / TIDAL / Visualizer tabs. TIDAL and the
// visualizer are dynamic (tidal_tab/viz_tab in /api/status): TIDAL appears
// once an account is connected, the visualizer hides while it is off (its
// switch stays available in settings → customize).
const TABS = new Set(['now', 'radio', 'tidal', 'viz']);
const LABELS = { now: 'tab_now', radio: 'tab_radio', tidal: 'tab_tidal', viz: 'tab_viz' };

export function Panel() {
  const { t } = useI18n();
  const { status } = useStatus();
  const [tab, setTab] = useState(() => {
    try { const s = localStorage.getItem('paneltab'); return TABS.has(s) ? s : 'now'; }
    catch { return 'now'; }
  });
  const order = ['now', 'radio',
                 ...(status && status.tidal_tab ? ['tidal'] : []),
                 ...(!status || status.viz_tab !== false ? ['viz'] : [])];
  const pick = (name) => {
    setTab(name);
    try { localStorage.setItem('paneltab', name); } catch { /* ignore */ }
  };
  // the active tab can vanish under us (viz switched off, TIDAL disconnected)
  // — but only judge that once the status actually arrived
  useEffect(() => {
    if (status && !order.includes(tab)) setTab('now');
  }, [status, order.join(','), tab]);
  // the homepage gesture (logo / player bar) — goHome() already persisted it
  useEffect(() => {
    const on = () => setTab('now');
    addEventListener('app:home', on);
    return () => removeEventListener('app:home', on);
  }, []);
  // swipe left → next tab, right → previous; clamped at the ends
  const step = (d) => {
    const j = order.indexOf(tab) + d;
    if (j >= 0 && j < order.length) pick(order[j]);
  };
  const swipe = useSwipe({ onLeft: () => step(1), onRight: () => step(-1) });

  return (
    <div class="swipe-col" {...swipe}>
      <Tabs active={tab} onChange={pick}
            items={order.map((id) => ({ id, label: t(LABELS[id]) }))} />
      {tab === 'now' && <NowTab />}
      {tab === 'radio' && <RadioTab />}
      {tab === 'tidal' && <TidalTab />}
      {tab === 'viz' && <VizTab />}
    </div>
  );
}

function NowTab() {
  const { status } = useStatus();
  const { t } = useI18n();
  const p = primary(status);
  const playing = !!(p && p.playing);

  // LMS serves the current track cover; proxied through the panel (see lmsArt).
  const artUrl = (p && p.id === 'lms' && p.playing && status && status.lms_playerid)
    ? lmsArt(`/music/current/cover.jpg?player=${encodeURIComponent(status.lms_playerid)}`
      + `&_t=${encodeURIComponent(p.detail || '')}`)
    : '';

  return (
    <section class="nowfill">
      {status && status.playing_count >= 2 && (
        <div class="card note">{t('warn_multi')}</div>
      )}
      <div class="now">
        <div class={'art' + (artUrl ? ' hasart' : '') + (playing ? ' playing' : '')}
             style={artUrl ? `background-image:url("${artUrl.replace(/"/g, '%22')}")` : ''}>
          <Eq n={5} on={playing} />
        </div>
        <div class="now-title">{p ? (p.detail || p.name) : t('js_silence')}</div>
        <div class="now-sub muted">{p ? srcSub(p) : ''}</div>
      </div>
    </section>
  );
}

function VizTab() {
  const { t } = useI18n();
  const [v, setV] = useState(null);
  const [msg, setMsg] = useState('');
  const [pending, setPending] = useState(null);   // optimistic switch state

  const refresh = async () => { try { setV(await apiGet('/api/viz')); } catch { /* keep */ } };
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 10000);
    return () => clearInterval(id);
  }, []);

  const engine = async (eng, shader) => {
    try { setMsg((await apiPost('/api/viz/engine', { engine: eng, shader: shader || '' })).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    refresh();
  };
  const preset = async (name) => {
    try { setMsg((await apiPost('/api/viz/preset', { name })).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    refresh();
  };
  const toggle = async () => {
    setPending(!on);
    try { setMsg((await apiPost('/api/viz/toggle')).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    await new Promise((r) => setTimeout(r, 600));   // the service takes a beat
    await refresh();
    setPending(null);
  };

  if (!v) return <div class="card"><p class="muted">…</p></div>;
  if (!v.installed) return <div class="card"><p class="muted">{t('viz_missing')}</p></div>;

  const on = pending != null ? pending : !!v.enabled;
  const glsl = v.engine === 'glsl';
  const items = glsl ? (v.shaders || []) : (v.presets || []);
  const current = glsl ? v.shader : v.preset;

  return (
    <div class="card">
      <div class="card-head">
        <h2>{t('tab_viz')}</h2>
        <label class="switch">
          <input type="checkbox" checked={on} onChange={toggle} />
          <span class="knob"></span>
        </label>
      </div>
      {v.hdmi_connected === false ? (
        <EmptyState icon="ico-plug-off" title={t('viz_hdmi_off')} sub={t('viz_hdmi_off_sub')} />
      ) : (
        <>
          <Collapsible open={on}>
            <Tabs compact active={v.engine} onChange={(id) => engine(id)}
                  items={[
                    { id: 'cava', label: t('viz_eng_cava') },
                    { id: 'glsl', label: t('viz_eng_glsl') + (v.glsl_available ? '' : ' ⚠'),
                      title: v.glsl_available ? '' : t('viz_glsl_missing') },
                  ]} />
            {glsl && v.glsl_error && <p class="muted">{t('js_glsl_err')}{v.glsl_error}</p>}
            <div class="vgrid">
              {items.map((it) => (
                <button key={it.id} class={'btn' + (it.id === current ? '' : ' sec')}
                        onClick={() => (glsl ? engine('glsl', it.id) : preset(it.id))}>
                  {it.label}{it.id === current ? ' ✓' : ''}
                </button>
              ))}
            </div>
            <p class="muted small">{t('viz_more')}</p>
          </Collapsible>
          {!on && <p class="muted">{t('viz_off_hint')}</p>}
        </>
      )}
      {msg && <p class="muted">{msg}</p>}
    </div>
  );
}
