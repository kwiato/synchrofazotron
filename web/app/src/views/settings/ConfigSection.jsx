import { useEffect, useRef, useState } from 'preact/hooks';
import { Browser } from '@capacitor/browser';
import { useI18n } from '../../i18n.jsx';
import { apiGet, apiPost } from '../../api.js';
import { useApi, doReboot } from '../../hooks.js';
import { useToast } from '../../components/Toast.jsx';
import { Droplet } from '../../components/Droplet.jsx';
import { WifiModal } from '../../components/WifiModal.jsx';
import { IS_APP, apiBase, switchDevice } from '../../host.js';
import { APP_SHA_SHORT, APK_URL, RELEASE_API } from '../../appversion.js';
import { ApkInstaller } from '../../apkinstaller.js';
import { radioFx, setRadioFx } from '../../prefs.js';

export function ConfigSection() {
  const { t } = useI18n();
  return (
    <section class="active">
      <div class="sect-title">{t('nav_config')}</div>
      <div class="cardgrid">
        <DeviceCard />
        <TailscaleCard />
        <UpdateCard />
        <RebootCard />
        <ExperimentalCard />
      </div>
    </section>
  );
}

// Experimental toggles. Normalize lives on the device (/api/viz/normalize);
// smooth radio loading is a local UI pref (prefs.js, this phone only).
function ExperimentalCard() {
  const { t } = useI18n();
  const [v, reload] = useApi('/api/viz', 0);
  const [busy, setBusy] = useState(false);
  const on = !!(v && v.normalize);
  const toggle = async (e) => {
    const val = e.currentTarget.checked;
    setBusy(true);
    try { await apiPost('/api/viz/normalize', { on: val }); } catch { /* ignore */ }
    await reload();
    setBusy(false);
  };
  const [fx, setFx] = useState(radioFx());
  const toggleFx = (e) => { const val = e.currentTarget.checked; setRadioFx(val); setFx(val); };
  return (
    <div class="card">
      <h2>🧪 {t('exp_head')}</h2>
      <p class="muted">{t('exp_note')}</p>
      <div class="card-head">
        <div>
          <b>{t('exp_normalize')}</b>
          <p class="muted small" style="margin:2px 0 0;">{t('exp_normalize_note')}</p>
        </div>
        <label class="switch">
          <input type="checkbox" checked={on} disabled={busy || !v} onChange={toggle} />
          <span class="knob"></span>
        </label>
      </div>
      <div class="card-head">
        <div>
          <b>{t('exp_radiofx')}</b>
          <p class="muted small" style="margin:2px 0 0;">{t('exp_radiofx_note')}</p>
        </div>
        <label class="switch">
          <input type="checkbox" checked={fx} onChange={toggleFx} />
          <span class="knob"></span>
        </label>
      </div>
    </div>
  );
}

// One card for everything device: which device the app is pointed at (app-only,
// with the switch button) and the device's broadcast name — merged from the old
// separate Device / Name cards.
function DeviceCard() {
  const { t, device } = useI18n();
  const [name, setName] = useState(device);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  const save = async () => {
    const v = name.trim();
    if (!v || !confirm(t('js_name_confirm'))) return;
    setBusy(true);
    setMsg(t('js_saving'));
    try {
      const j = await apiPost('/api/name', { name: v });
      setMsg(j.message || '');
      // hostname/URL may have changed — reload so the panel shows the new name
      if (j.ok) setTimeout(() => location.reload(), 2500);
    } catch { setMsg(t('js_conn_error')); }
    setBusy(false);
  };

  return (
    <div class="card">
      <h2><i class="ico ico-link"></i> {t('device_head')}</h2>
      {IS_APP && (
        <>
          <p class="muted">{t('device_connected')}: <code>{apiBase()}</code></p>
          <button class="btn sec" onClick={switchDevice}>{t('switch_device')}</button>
          <div class="subhead muted">{t('name_head')}</div>
        </>
      )}
      <p class="muted">{t('name_note')}</p>
      <input value={name} maxLength={32} placeholder={t('name_ph')} autocomplete="off"
             onInput={(e) => setName(e.currentTarget.value)} />
      <button class="btn sec" disabled={busy} onClick={save}>{t('name_save')}</button>
      {msg && <p class="muted">{msg}</p>}
    </div>
  );
}

// Wi-Fi: current connection + saved networks + add, in one card. Self-contained
// (fetches its own state) so any section can drop it in.
export function WifiCard() {
  const { t } = useI18n();
  const [w, reload] = useApi('/api/wifi', 8000);
  const [modal, setModal] = useState(false);
  const [msg, setMsg] = useState('');
  const cur = w && w.current;
  const saved = (w && w.saved) || [];

  const parts = [];
  if (cur && cur.ip) parts.push(<span>{t('js_lan_ip')}<code>{cur.ip}</code></span>);
  if (w && w.tailscale_ip) parts.push(<span>{t('js_ts_ip')}<code>{w.tailscale_ip}</code></span>);
  if (w && w.hostname) parts.push(<span><code>{w.hostname}</code></span>);

  const remove = async (slot, ssid) => {
    if (!confirm(t('js_rm_pre') + ssid + t('js_rm_suf'))) return;
    try { setMsg((await apiPost('/api/wifi/remove', { slot })).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    reload();
  };

  return (
    <div class="card">
      <h2><i class="ico ico-wifi"></i> {t('wifi_now_head')}</h2>
      <p class="muted">
        {cur
          ? <><span class="pill on">{t('js_wifi_connected')}</span> <b>{cur.ssid}</b>
              {cur.ip ? ' — ' + cur.ip : ''}
              {cur.signal != null && <span class="muted"> ({cur.signal} dBm)</span>}</>
          : <span class="pill off">{t('js_wifi_none')}</span>}
      </p>
      <p class="muted">{parts.map((p, i) => <span key={i}>{i ? ' · ' : ''}{p}</span>)}</p>

      <div class="subhead muted">{t('wifi_saved_head')}</div>
      <div>
        {saved.length
          ? saved.map((s) => (
              <div class="row" key={s.slot}>
                <div class="info">
                  {cur && cur.ssid === s.ssid && <i class="dot on"></i>}{' '}
                  <b>{s.ssid}</b> <span class="muted">{t('js_slot')}{s.slot}</span>
                </div>
                <button class="xbtn" title={t('js_remove')} onClick={() => remove(s.slot, s.ssid)}>
                  <i class="ico ico-trash"></i>
                </button>
              </div>))
          : <p class="muted">{t('js_no_saved')}</p>}
      </div>
      <button class="btn sec" onClick={() => setModal(true)}>{t('wifi_add_btn')}</button>
      {msg && <p class="muted">{msg}</p>}
      <details class="muted">
        <summary>{t('how_head')}</summary>
        <p>{t('how_note')}</p>
      </details>
      <WifiModal open={modal} onClose={() => setModal(false)}
                 onAdded={(m) => { setMsg(m); reload(); }} />
    </div>
  );
}

function TailscaleCard() {
  const { t } = useI18n();
  const [ts, reload] = useApi('/api/tailscale', 15000);
  const [msg, setMsg] = useState('');
  const installed = !!(ts && ts.installed);
  const active = !!(ts && ts.active);

  const toggle = async (e) => {
    const up = e.currentTarget.checked;
    if (!up && !confirm(t('js_src_off_pre') + 'Tailscale' + t('js_src_off_suf'))) { reload(); return; }
    try { setMsg((await apiPost('/api/tailscale/set', { up })).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    reload();
  };

  return (
    <div class="card">
      <div class="card-head">
        <h2><i class="ico ico-link"></i> {t('ts_head')}</h2>
        <label class="switch">
          <input type="checkbox" checked={active} disabled={!installed} onChange={toggle} />
          <span class="knob"></span>
        </label>
      </div>
      <p class="muted">{t('ts_note')}</p>
      <p class="muted">
        {!installed ? t('ts_missing')
          : active
            ? <><span class="pill on">{t('js_wifi_connected')}</span>{ts.ip && <> <code>{ts.ip}</code></>}</>
            : <span class="pill off">{t('js_off')}</span>}
      </p>
      {msg && <p class="muted">{msg}</p>}
    </div>
  );
}

export function AudioOutputCard() {
  const { t } = useI18n();
  const toast = useToast();
  const [a, reload] = useApi('/api/audio', 0);
  const [msg, setMsg] = useState('');
  const [testing, setTesting] = useState(false);
  const [rebooting, setRebooting] = useState(false);

  const set = async (mode) => {
    if (!confirm(t('js_audio_confirm'))) return;
    try { setMsg((await apiPost('/api/audio/set', { output: mode })).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    reload();
  };
  const test = async () => {
    setTesting(true);
    setMsg(t('js_bt_testing'));
    try { setMsg((await apiPost('/api/audio/test')).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    setTesting(false);
  };
  const reboot = () => doReboot({
    t, toast,
    onStart: () => { setRebooting(true); setMsg(t('js_rebooting')); },
    onDone: () => { setRebooting(false); setMsg(''); },
  });

  const cards = (a && a.cards) || {};
  const out = a && a.output;
  const rebootReq = a && a.reboot_required;
  // HDMI: the ALSA card exists even with no monitor, but audio only plays to a
  // connected display — so green requires both. Amber = card up, no monitor.
  const hdmiNoDisp = a && a.hdmi_connected === false;
  const hdmiDot = !cards.hdmi ? 'err' : (hdmiNoDisp ? 'warn' : 'on');
  const dot = (ok) => <i class={'dot ' + (ok ? 'on' : 'err')}></i>;

  return (
    <div class="card">
      <h2><i class="ico ico-volume"></i> {t('audio_head')}</h2>
      <p class="muted">{t('audio_out_note')}</p>
      <div class="lrow">
        <button class={'btn' + (out === 'dac' ? '' : ' sec')} onClick={() => set('dac')}>
          {dot(cards.dac)} DAC{out === 'dac' ? ' ✓' : ''}
        </button>
        <button class={'btn' + (out === 'hdmi' ? '' : ' sec')} onClick={() => set('hdmi')}
                title={hdmiNoDisp ? t('audio_hdmi_nodisp') : ''}>
          <i class={'dot ' + hdmiDot}></i> HDMI{out === 'hdmi' ? ' ✓' : ''}
        </button>
      </div>
      <button class="btn sec" disabled={testing} onClick={test}>
        <i class="ico ico-play"></i> {t('audio_test_btn')}
      </button>
      {rebootReq && <button class="btn sec" disabled={rebooting} onClick={reboot}>{t('js_reboot')}</button>}
      {out === 'hdmi' && hdmiNoDisp && <p class="muted">{t('audio_hdmi_nodisp')}</p>}
      <p class="muted">
        {rebooting && <span class="spinner"></span>}{' '}
        {msg || (rebootReq ? t('js_audio_reboot') : '')}
      </p>
    </div>
  );
}

// 'system' follows the OS light/dark preference, resolving to one of the mono
// themes (the only ones the stylesheet knows besides the attribute-less neon).
const sysTheme = () =>
  matchMedia('(prefers-color-scheme: dark)').matches ? 'mono-dark' : 'mono-light';

// Apply a stored choice to <html>: 'system' tracks the OS, 'neon' is the
// attribute-less default, everything else maps straight onto data-theme. Kept in
// sync with the no-flash script in index.html.
function applyTheme(v) {
  const eff = v === 'system' ? sysTheme() : v;
  if (eff === 'neon') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = eff;
}

// Appearance & language in one card: language (server-side, reloads) + theme
// (client-only: sets data-theme on <html>, live, no round-trip).
export function AppearanceCard() {
  const { t, lang } = useI18n();
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('theme') || 'system'; } catch { return 'system'; }
  });
  // While on 'system', re-apply when the OS flips between light and dark.
  useEffect(() => {
    if (theme !== 'system') return;
    const mq = matchMedia('(prefers-color-scheme: dark)');
    const on = () => applyTheme('system');
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, [theme]);
  const changeTheme = (e) => {
    const v = e.currentTarget.value;
    setTheme(v);
    try { localStorage.setItem('theme', v); } catch { /* private mode */ }
    applyTheme(v);
  };
  const changeLang = async (e) => {
    const l = e.currentTarget.value;
    try { await apiPost('/api/lang', { lang: l }); } catch { /* ignore */ }
    location.reload();
  };

  return (
    <div class="card">
      <h2><i class="ico ico-brush"></i> {t('appearance_head')}</h2>
      <label class="fieldlabel muted">{t('lang_head')}</label>
      <select value={lang} onChange={changeLang}>
        <option value="en">English</option>
        <option value="pl">Polski</option>
      </select>
      <label class="fieldlabel muted">{t('theme_head')}</label>
      <select value={theme} onChange={changeTheme}>
        <option value="system">{t('theme_system')}</option>
        <option value="mono-light">{t('theme_mono_light')}</option>
        <option value="mono-dark">{t('theme_mono_dark')}</option>
        <option value="neon">{t('theme_neon')}</option>
      </select>
    </div>
  );
}

const iconFor = (tone) => (tone === 'danger' ? 'x' : tone === 'warn' ? 'dot' : 'check');

function UpdateCard() {
  const { t } = useI18n();
  const [msg, setMsg] = useState('');
  const [msgTone, setMsgTone] = useState('');
  const [checking, setChecking] = useState(false);
  const [running, setRunning] = useState(false);
  const [topDrop, setTopDrop] = useState(null);        // top droplet {open,text,tone,icon,spinner}
  const timer = useRef(null);
  const runTimers = useRef([]);
  const closeTopLater = (closeMs, reloadMs) => {
    runTimers.current.push(setTimeout(() => setTopDrop((d) => (d ? { ...d, open: false } : d)), closeMs));
    if (reloadMs) runTimers.current.push(setTimeout(() => location.reload(), reloadMs));
  };
  // App-update half (mobile shell only): compares the installed build's SHA
  // against the latest release; "install" downloads the APK natively (see
  // apkinstaller.js) and fires the system package installer.
  const [appMsg, setAppMsg] = useState('');
  const [appMsgTone, setAppMsgTone] = useState('');
  const [appChecking, setAppChecking] = useState(false);
  const [appAvail, setAppAvail] = useState(false);
  const [appBusy, setAppBusy] = useState(false);

  const appCheck = async () => {
    setAppChecking(true);
    setAppMsg(t('js_upd_checking')); setAppMsgTone('');
    try {
      const r = await fetch(`${RELEASE_API}?_=${Date.now()}`, { cache: 'no-store' });
      if (!r.ok) throw new Error(String(r.status));
      const m = ((await r.json()).body || '').match(/[0-9a-f]{7,40}/i);
      const latest = m ? m[0].slice(0, 7) : '';
      const isNew = !!latest && latest !== APP_SHA_SHORT;
      setAppAvail(isNew);
      setAppMsg(isNew ? t('appupd_available') : t('appupd_current'));
      setAppMsgTone(isNew ? 'warn' : 'good');
    } catch {
      setAppMsg(t('js_upd_checkfail')); setAppMsgTone('danger');
    }
    setAppChecking(false);
  };
  const appRun = async () => {
    setAppBusy(true);
    let sub = null;
    try {
      // Android 8+ needs a one-time per-app "install unknown apps" grant; send
      // the user to the system screen and let them tap the button again.
      if (!(await ApkInstaller.canInstall()).allowed) {
        setAppMsg(t('appupd_allow')); setAppMsgTone('warn');
        await ApkInstaller.openInstallSettings();
        return;
      }
      setAppMsg(t('appupd_downloading')); setAppMsgTone('');
      sub = await ApkInstaller.addListener('progress', ({ received, total }) => {
        setAppMsg(t('appupd_downloading')
          + (total > 0 ? ` ${Math.round((received / total) * 100)}%` : ''));
      });
      await ApkInstaller.downloadAndInstall({ url: APK_URL });
      setAppMsg(t('appupd_installing')); setAppMsgTone('good');
    } catch {
      // native path failed (or web build) — fall back to the browser download
      setAppMsg(t('appupd_dl_fail')); setAppMsgTone('danger');
      try { await Browser.open({ url: APK_URL }); } catch { /* ignore */ }
    } finally {
      if (sub) sub.remove();
      setAppBusy(false);
    }
  };

  const poll = () => {
    if (timer.current) return;
    setRunning(true);
    setMsg(''); setMsgTone('');                       // the run lives in the top droplet
    setTopDrop({ open: true, text: t('js_upd_running'), tone: '', icon: 'check', spinner: true });
    timer.current = setInterval(async () => {
      try {
        const j = await apiGet('/api/update');
        if (j.running) return;
        clearInterval(timer.current);
        timer.current = null;
        setRunning(false);
        if (j.failed) {
          setTopDrop({ open: true, text: t('js_upd_failed'), tone: 'danger', icon: 'x', spinner: false });
          closeTopLater(2400);
        } else {
          setTopDrop({ open: true, text: t('js_upd_done'), tone: 'good', icon: 'check', spinner: false });
          closeTopLater(1300, 2300);                  // show the check, ripple away, then reload
        }
      } catch { /* panel restarting mid-update — keep polling */ }
    }, 3000);
  };

  // page opened while an update is already running -> resume the poll
  useEffect(() => {
    apiGet('/api/update').then((j) => { if (j.running) poll(); }).catch(() => {});
    return () => {
      if (timer.current) clearInterval(timer.current);
      runTimers.current.forEach(clearTimeout);
    };
  }, []);

  const check = async () => {
    setChecking(true);
    setMsg(t('js_upd_checking')); setMsgTone('');
    try {
      const j = await apiGet('/api/update/check');
      if (!j.ok) { setMsg(t('js_upd_checkfail')); setMsgTone('danger'); }
      else if (j.update_available) { setMsg(t('js_upd_available')); setMsgTone('warn'); }
      else { setMsg(t('js_upd_current')); setMsgTone('good'); }
    } catch { setMsg(t('js_conn_error')); setMsgTone('danger'); }
    setChecking(false);
  };
  const run = async () => {
    if (!confirm(t('js_upd_confirm'))) return;
    try {
      const j = await apiPost('/api/update/run');
      if (!j.ok) {
        setTopDrop({ open: true, text: j.message || t('js_error'), tone: 'danger', icon: 'x', spinner: false });
        closeTopLater(2400);
        return;
      }
      poll();
    } catch {
      setTopDrop({ open: true, text: t('js_conn_error'), tone: 'danger', icon: 'x', spinner: false });
      closeTopLater(2400);
    }
  };

  return (
    <div class="card">
      <h2><i class="ico ico-refresh"></i> {t('upd_head')}</h2>
      <p class="muted">{t('upd_note')}</p>
      <div class="lrow">
        <button class="btn sec" disabled={checking} onClick={check}>{t('upd_check_btn')}</button>
        <button class="btn sec" disabled={running} onClick={run}>{t('upd_run_btn')}</button>
      </div>
      {msg && (
        <Droplet inline open text={msg} tone={msgTone}
                 spinner={checking} icon={iconFor(msgTone)} />
      )}

      {IS_APP && (
        <>
          <div class="subhead muted">{t('appupd_head')} · {APP_SHA_SHORT}</div>
          <p class="muted">{t('appupd_note')}</p>
          <div class="lrow">
            <button class="btn sec" disabled={appChecking || appBusy} onClick={appCheck}>{t('upd_check_btn')}</button>
            <button class={'btn' + (appAvail ? '' : ' sec')} disabled={appBusy}
                    onClick={appRun}>{t('appupd_run_btn')}</button>
          </div>
          {appMsg && (
            <Droplet inline open text={appMsg} tone={appMsgTone}
                     spinner={appChecking || appBusy} icon={iconFor(appMsgTone)} />
          )}
        </>
      )}

      {topDrop && (
        <Droplet open={topDrop.open} text={topDrop.text} tone={topDrop.tone}
                 spinner={topDrop.spinner} icon={topDrop.icon} />
      )}
    </div>
  );
}

function RebootCard() {
  const { t } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const reboot = () => doReboot({
    t, toast,
    onStart: () => { setBusy(true); setMsg(t('js_rebooting')); },
    onDone: () => { setBusy(false); setMsg(''); },
  });
  return (
    <div class="card">
      <h2><i class="ico ico-refresh"></i> {t('reboot_head')}</h2>
      <p class="muted">{t('reboot_note')}</p>
      <button class="btn sec" disabled={busy} onClick={reboot}>{t('js_reboot')}</button>
      <p class="muted">{busy && <span class="spinner"></span>}{' '}{msg}</p>
    </div>
  );
}
