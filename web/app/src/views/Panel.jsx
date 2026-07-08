import { useEffect, useState } from 'preact/hooks';
import { useStatus } from '../status.jsx';
import { useI18n } from '../i18n.jsx';
import { apiGet, apiPost } from '../api.js';
import { primary, srcSub } from '../util.js';
import { Eq } from '../components/Eq.jsx';

// Main view: the Now / Visualizer tabs. Ported from panel.js.
export function Panel() {
  const { t } = useI18n();
  const [tab, setTab] = useState(() => {
    try { return localStorage.getItem('paneltab') === 'viz' ? 'viz' : 'now'; }
    catch { return 'now'; }
  });
  const pick = (name) => {
    setTab(name);
    try { localStorage.setItem('paneltab', name); } catch { /* ignore */ }
  };

  return (
    <>
      <nav class="tabs">
        <button class={'tab' + (tab === 'now' ? ' active' : '')} onClick={() => pick('now')}>{t('tab_now')}</button>
        <button class={'tab' + (tab === 'viz' ? ' active' : '')} onClick={() => pick('viz')}>{t('tab_viz')}</button>
      </nav>
      {tab === 'now' ? <NowTab /> : <VizTab />}
    </>
  );
}

function NowTab() {
  const { status } = useStatus();
  const { t, lmsPort } = useI18n();
  const p = primary(status);
  const playing = !!(p && p.playing);

  // LMS serves the current track cover itself; other sources have no art.
  const artUrl = (p && p.id === 'lms' && p.playing && status && status.lms_playerid)
    ? `http://${location.hostname}:${lmsPort}/music/current/cover.jpg`
      + `?player=${encodeURIComponent(status.lms_playerid)}`
      + `&_t=${encodeURIComponent(p.detail || '')}`
    : '';

  return (
    <section>
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
    try { setMsg((await apiPost('/api/viz/toggle')).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    setTimeout(refresh, 500);
  };

  if (!v) return <div class="card"><p class="muted">…</p></div>;
  if (!v.installed) return <div class="card"><p class="muted">{t('viz_missing')}</p></div>;

  const glsl = v.engine === 'glsl';
  const items = glsl ? (v.shaders || []) : (v.presets || []);
  const current = glsl ? v.shader : v.preset;

  return (
    <div class="card">
      <div class="lrow">
        <button class={'btn' + (glsl ? ' sec' : '')} onClick={() => engine('cava')}>{t('viz_eng_cava')}</button>
        <button class={'btn' + (glsl ? '' : ' sec')}
                title={v.glsl_available ? '' : t('viz_glsl_missing')}
                onClick={() => engine('glsl')}>
          {t('viz_eng_glsl')}{v.glsl_available ? '' : ' ⚠'}
        </button>
      </div>
      {glsl && v.glsl_error && <p class="muted">{t('js_glsl_err')}{v.glsl_error}</p>}
      <div class="vgrid">
        {items.map((it) => (
          <button key={it.id} class={'btn' + (it.id === current ? '' : ' sec')}
                  onClick={() => (glsl ? engine('glsl', it.id) : preset(it.id))}>
            {it.label}{it.id === current ? ' ✓' : ''}
          </button>
        ))}
      </div>
      <button class="btn sec" onClick={toggle}>{v.active ? t('js_viz_stop') : t('js_viz_start')}</button>
      {msg && <p class="muted">{msg}</p>}
      <p class="muted small">{t('viz_more')}</p>
    </div>
  );
}
