import { useCallback, useEffect, useRef, useState } from 'preact/hooks';
import { useI18n } from '../../i18n.jsx';
import { apiGet, apiPost } from '../../api.js';
import { useApi } from '../../hooks.js';
import { WifiCard } from './ConfigSection.jsx';

// Numbered how-to step whose i18n string carries inline HTML (<b>NAME</b>) —
// rendering it as text showed the literal tags.
function Step({ n, html }) {
  return <p><span class="num">{n}</span><span dangerouslySetInnerHTML={{ __html: html }} /></p>;
}

export function ConnectionsSection() {
  const { t, lmsPort } = useI18n();
  const [src, reload] = useApi('/api/sources', 10000);
  const groups = (src && src.sources) || [];
  const g = (id) => groups.find((x) => x.id === id);
  const lmsUrl = `http://${location.hostname}:${lmsPort}/material`;
  const spotify = g('spotify');

  return (
    <section class="active">
      <div class="sect-title">{t('nav_connections')}</div>
      <div class="cardgrid">
        <WifiCard />
        <BluetoothCard group={g('bluetooth')} reloadSources={reload} />

        <SourceCard group={g('airplay')} reload={reload} icon="ico-airplay" title={t('airplay_head')}>
          <Step n="1" html={t('airplay_1')} />
          <Step n="2" html={t('airplay_2')} />
        </SourceCard>

        <SourceCard group={g('lms')} reload={reload} icon="ico-music" title={t('lms_head')}>
          <Step n="1" html={t('lms_1')} />
          <Step n="2" html={t('lms_2')} />
          <p>{t('lms_web')} <a href={lmsUrl}>{lmsUrl}</a> {t('lms_web2')}</p>
        </SourceCard>

        <TidalCard />

        {spotify && (
          <SourceCard group={spotify} reload={reload} icon="ico-music" title={t('spotify_head')}>
            <Step n="1" html={t('spotify_1')} />
            <Step n="2" html={t('spotify_2')} />
            <p class="muted">{t('spotify_note')}</p>
          </SourceCard>
        )}
      </div>
    </section>
  );
}

// TIDAL account, connected through the LMS plugin's OAuth device flow. The
// panel proxies the plugin's auth page: "connect" fetches a link.tidal.com
// URL + device code, the user signs in on this phone, and LMS polls TIDAL
// itself — we only poll the panel until the account shows up. The head switch
// merely hides TIDAL on the main screen (source label); it never signs out.
function TidalCard() {
  const { t } = useI18n();
  const [st, setSt] = useState(null);       // /api/tidal payload
  const [auth, setAuth] = useState(null);   // {link, code} while a flow runs
  const [err, setErr] = useState('');
  const poll = useRef(null);

  const load = useCallback(async () => {
    try { setSt(await apiGet('/api/tidal')); } catch { setSt(null); }
  }, []);
  useEffect(() => { load(); return () => clearInterval(poll.current); }, [load]);

  const connect = async () => {
    setErr('');
    try {
      const j = await apiPost('/api/tidal/auth/start', {});
      if (!j.ok) { setErr(t('js_conn_error')); return; }
      const before = ((st && st.accounts) || []).length;
      setAuth(j);
      clearInterval(poll.current);
      poll.current = setInterval(async () => {
        try {
          const s = await apiGet('/api/tidal/auth/status?code=' + encodeURIComponent(j.code));
          if (!s.done) return;
          // "done" also fires when the code expires — success means an
          // account actually appeared
          clearInterval(poll.current);
          setAuth(null);
          if (((s.accounts) || []).length <= before) setErr(t('tidal_expired'));
          load();
        } catch { /* panel briefly unreachable — keep polling */ }
      }, 2000);
    } catch { setErr(t('js_conn_error')); }
  };

  const forget = async (a) => {
    if (!confirm(t('tidal_forget_confirm'))) return;
    try { await apiPost('/api/tidal/forget', { id: a.id }); } catch { /* reload below */ }
    load();
  };

  // one-tap plugin install (devices set up before setup.sh grew the TIDAL
  // step): the panel does the LMS "Manage plugins" POST + LMS restart; we
  // poll /api/tidal until the plugin answers (or the panel reports an error)
  const install = async () => {
    setErr('');
    try {
      await apiPost('/api/tidal/install', {});
      setSt((s) => (s ? { ...s, installing: true } : s));
      clearInterval(poll.current);
      let tries = 0;
      poll.current = setInterval(async () => {
        try {
          const s = await apiGet('/api/tidal');
          if (s.installing && ++tries < 160) return;
          clearInterval(poll.current);
          setSt(s);
          if (!s.available) setErr(t('tidal_install_err'));
        } catch { /* LMS restarting can stall the panel briefly — keep polling */ }
      }, 3000);
    } catch { setErr(t('js_conn_error')); }
  };

  const toggleShow = async (e) => {
    const show = e.currentTarget.checked;
    setSt((s) => (s ? { ...s, show } : s));
    try { await apiPost('/api/tidal/show', { show }); } catch { load(); }
  };

  const accounts = (st && st.accounts) || [];
  const installing = !!(st && st.installing);

  return (
    <div class="card">
      <div class="card-head">
        <h2><i class="ico ico-music"></i> {t('tidal_head')}</h2>
        <label class="switch" title={t('tidal_show_note')}>
          <input type="checkbox" checked={!!(st && st.show)} onChange={toggleShow} />
          <span class="knob"></span>
        </label>
      </div>
      <p class="muted">{t('tidal_note')}</p>

      {st && !st.available && (installing
        ? <p class="muted small"><span class="spinner"></span>{t('tidal_installing')}</p>
        : <>
            <p class="muted">{t('tidal_missing')}</p>
            <button class="btn" onClick={install}>{t('tidal_install')}</button>
          </>)}
      {st && st.available && accounts.map((a) => (
        <div key={a.id}>
          <div class="row">
            <div class="info">{t('tidal_logged')} <b>{a.name}</b></div>
          </div>
          <button class="btn sec" onClick={() => forget(a)}>{t('tidal_forget')}</button>
        </div>
      ))}
      {st && st.available && !accounts.length && (auth
        ? <>
            <p class="muted">{t('tidal_link_note')}</p>
            <a class="btn tidal-link" href={auth.link} target="_blank" rel="noreferrer">
              {auth.link.replace(/^https?:\/\//, '')}
            </a>
            <p class="muted small"><span class="spinner"></span>{t('tidal_waiting')}</p>
          </>
        : <button class="btn" onClick={connect}>{t('tidal_connect')}</button>)}
      {err && <p class="muted">{err}</p>}

      <p class="muted small">{t('tidal_show_note')}</p>
    </div>
  );
}

// Enable/disable switch + service status dots, shared by AirPlay / LMS / Spotify.
function SourceCard({ group, reload, icon, title, children }) {
  const { t } = useI18n();
  const [msg, setMsg] = useState('');
  const installed = !!(group && group.installed);
  const enabled = !!(group && group.enabled);
  const services = (group && group.services) || [];

  const toggle = async (e) => {
    const enable = e.currentTarget.checked;
    if (!enable && !confirm(t('js_src_off_pre') + (group.label || group.id) + t('js_src_off_suf'))) {
      reload();
      return;
    }
    try { setMsg((await apiPost('/api/source/toggle', { source: group.id, enable })).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    reload();
  };

  return (
    <div class="card">
      <div class="card-head">
        <h2><i class={'ico ' + icon}></i> {title}</h2>
        <label class="switch">
          <input type="checkbox" checked={enabled} disabled={!installed} onChange={toggle} />
          <span class="knob"></span>
        </label>
      </div>
      {children}
      {installed && !enabled && <p class="muted">{t('src_disabled_hint')}</p>}
      {msg && <p class="muted">{msg}</p>}
      <Dots installed={installed} enabled={enabled} services={services} />
    </div>
  );
}

function Dots({ installed, enabled, services }) {
  const { t } = useI18n();
  if (!installed) return <div class="dots"><span class="pill off">{t('src_not_installed')}</span></div>;
  return (
    <div class="dots">
      {services.map((s) => (
        <span key={s.name}>
          <i class={'dot ' + (s.active ? 'on' : (enabled ? 'err' : ''))}></i>{s.name}
        </span>))}
    </div>
  );
}

// Bluetooth is the one source with live device management: pair list, connect /
// disconnect / forget, plus the periodic auto-reconnect toggle.
function BluetoothCard({ group, reloadSources }) {
  const { t } = useI18n();
  const [bt, setBt] = useState(null);
  const [msg, setMsg] = useState('');
  const [srcMsg, setSrcMsg] = useState('');
  const [report, setReport] = useState(null);
  const [rcEnabled, setRcEnabled] = useState(false);
  const [rcInterval, setRcInterval] = useState(60);
  const busy = useRef(false);        // do not repaint the list mid-connect
  const firstReconnect = useRef(true);

  const load = useCallback(async () => {
    if (busy.current) return;
    try {
      const b = await apiGet('/api/bt');
      setBt(b);
      // sync the reconnect controls once; after that they are user-owned so a
      // background poll never stomps a switch/slider mid-interaction
      if (firstReconnect.current && b.reconnect) {
        setRcEnabled(b.reconnect.enabled);
        setRcInterval(b.reconnect.interval);
        firstReconnect.current = false;
      }
    } catch { /* keep last */ }
  }, []);
  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  const saveReconnect = async (enabled, interval) => {
    try { await apiPost('/api/bt/reconnect', { enabled, interval }); } catch { /* ignore */ }
  };

  const connect = async (mac) => {
    if (busy.current) return;
    busy.current = true;
    setMsg(t('js_bt_connecting'));
    try { setMsg((await apiPost('/api/bt/connect', { mac })).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    busy.current = false;
    load();
  };
  const disconnect = async (mac) => {
    busy.current = true;
    try { setMsg((await apiPost('/api/bt/disconnect', { mac })).message || ''); }
    catch { /* ignore */ }
    busy.current = false;
    load();
  };
  const forget = async (mac, name) => {
    if (!confirm(t('js_bt_forget_pre') + name + t('js_bt_forget_suf'))) return;
    busy.current = true;
    try { setMsg((await apiPost('/api/bt/forget', { mac })).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    busy.current = false;
    load();
  };
  const debug = async () => {
    setReport('…');
    try { setReport((await apiGet('/api/bt/debug')).report || ''); }
    catch { setReport(t('js_conn_error')); }
  };

  const toggleSrc = async (e) => {
    const enable = e.currentTarget.checked;
    if (!enable && !confirm(t('js_src_off_pre') + ((group && group.label) || 'Bluetooth') + t('js_src_off_suf'))) {
      reloadSources();
      return;
    }
    try { setSrcMsg((await apiPost('/api/source/toggle', { source: 'bluetooth', enable })).message || ''); }
    catch { setSrcMsg(t('js_conn_error')); }
    reloadSources();
    load();
  };

  const installed = !!(group && group.installed);
  const enabled = !!(group && group.enabled);
  const paired = (bt && bt.paired) || [];

  return (
    <div class="card">
      <div class="card-head">
        <h2><i class="ico ico-bt"></i> {t('bt_head')}</h2>
        <label class="switch">
          <input type="checkbox" checked={enabled} disabled={!installed} onChange={toggleSrc} />
          <span class="knob"></span>
        </label>
      </div>
      <p class="muted" dangerouslySetInnerHTML={{ __html: t('bt_intro') }} />
      <p class="muted" dangerouslySetInnerHTML={{ __html: t('bt_after') }} />

      <h3>{t('bts_head')}</h3>
      <p class="muted">{t('bts_note')}</p>
      <div>
        {paired.length
          ? paired.map((d) => (
              <div class="row" key={d.mac}>
                <div class="info" style="cursor:pointer;" onClick={() => connect(d.mac)}>
                  <i class={'dot' + (d.connected ? ' on' : '')}></i> <b>{d.name}</b>
                </div>
                {d.connected && (
                  <button class="xbtn" title={t('js_bt_disconnect')} onClick={() => disconnect(d.mac)}>✕</button>
                )}
                <button class="xbtn" title={t('bt_forget_title')} onClick={() => forget(d.mac, d.name)}>
                  <i class="ico ico-trash"></i>
                </button>
              </div>))
          : <p class="muted">{t('js_bt_none')}</p>}
      </div>
      {msg && <p class="muted">{msg}</p>}
      <button class="btn sec" onClick={debug}>{t('bts_debug_btn')}</button>
      {report != null && <pre>{report}</pre>}

      <div class="card-head" style="margin-top:14px;">
        <h3 style="margin:0;">{t('bt_reconnect_label')}</h3>
        <label class="switch">
          <input type="checkbox" checked={rcEnabled}
                 onChange={(e) => { const v = e.currentTarget.checked; setRcEnabled(v); saveReconnect(v, rcInterval); }} />
          <span class="knob"></span>
        </label>
      </div>
      <p class="muted">{t('bt_reconnect_note')}</p>
      <label class="vlabel">{t('bt_interval_label')}: <b>{rcInterval}</b>
        <input type="range" min="10" max="300" step="5" value={rcInterval} disabled={!rcEnabled}
               onInput={(e) => setRcInterval(+e.currentTarget.value)}
               onChange={(e) => saveReconnect(rcEnabled, +e.currentTarget.value)} />
      </label>

      {installed && !enabled && <p class="muted">{t('src_disabled_hint')}</p>}
      {srcMsg && <p class="muted">{srcMsg}</p>}
      <Dots installed={installed} enabled={enabled} services={(group && group.services) || []} />
    </div>
  );
}
