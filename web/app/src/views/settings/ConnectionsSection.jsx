import { useCallback, useEffect, useRef, useState } from 'preact/hooks';
import { useI18n } from '../../i18n.jsx';
import { apiGet, apiPost } from '../../api.js';
import { useApi } from '../../hooks.js';
import { WifiCard } from './ConfigSection.jsx';

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
          <p><span class="num">1</span>{t('airplay_1')}</p>
          <p><span class="num">2</span>{t('airplay_2')}</p>
        </SourceCard>

        <SourceCard group={g('lms')} reload={reload} icon="ico-music" title={t('lms_head')}>
          <p><span class="num">1</span>{t('lms_1')}</p>
          <p><span class="num">2</span>{t('lms_2')}</p>
          <p>{t('lms_web')} <a href={lmsUrl}>{lmsUrl}</a> {t('lms_web2')}</p>
        </SourceCard>

        {spotify && (
          <SourceCard group={spotify} reload={reload} icon="ico-music" title={t('spotify_head')}>
            <p><span class="num">1</span>{t('spotify_1')}</p>
            <p><span class="num">2</span>{t('spotify_2')}</p>
            <p class="muted">{t('spotify_note')}</p>
          </SourceCard>
        )}

        <div class="card note">
          <h2><i class="ico ico-info"></i> {t('audio_note_head')}</h2>
          <p class="muted">{t('audio_note')}</p>
        </div>
      </div>
    </section>
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
