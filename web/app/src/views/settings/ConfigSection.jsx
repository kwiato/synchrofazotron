import { useEffect, useRef, useState } from 'preact/hooks';
import { Browser } from '@capacitor/browser';
import { useI18n } from '../../i18n.jsx';
import { apiGet, apiPost } from '../../api.js';
import { useApi, doReboot } from '../../hooks.js';
import { useToast } from '../../components/Toast.jsx';
import { WifiModal } from '../../components/WifiModal.jsx';
import { IS_APP } from '../../host.js';
import { APP_SHA_SHORT, APK_URL, VERSION_URL } from '../../appversion.js';

export function ConfigSection() {
  const { t } = useI18n();
  const [w, reloadW] = useApi('/api/wifi', 8000);
  return (
    <section class="active">
      <div class="sect-title">{t('nav_config')}</div>
      <div class="cardgrid">
        <NameCard />
        <WifiNowCard w={w} />
        <SavedNetworksCard w={w} reload={reloadW} />
        <TailscaleCard />
        <AudioOutputCard />
        <LanguageCard />
        <ThemeCard />
        <UpdateCard />
        {IS_APP && <AppUpdateCard />}
        <RebootCard />
      </div>
    </section>
  );
}

function NameCard() {
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
      <h2><i class="ico ico-cog"></i> {t('name_head')}</h2>
      <p class="muted">{t('name_note')}</p>
      <input value={name} maxLength={32} placeholder={t('name_ph')} autocomplete="off"
             onInput={(e) => setName(e.currentTarget.value)} />
      <button class="btn sec" disabled={busy} onClick={save}>{t('name_save')}</button>
      {msg && <p class="muted">{msg}</p>}
    </div>
  );
}

function WifiNowCard({ w }) {
  const { t } = useI18n();
  const cur = w && w.current;
  const parts = [];
  if (cur && cur.ip) parts.push(<span>{t('js_lan_ip')}<code>{cur.ip}</code></span>);
  if (w && w.tailscale_ip) parts.push(<span>{t('js_ts_ip')}<code>{w.tailscale_ip}</code></span>);
  if (w && w.hostname) parts.push(<span><code>{w.hostname}</code></span>);

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
    </div>
  );
}

function SavedNetworksCard({ w, reload }) {
  const { t } = useI18n();
  const [modal, setModal] = useState(false);
  const [msg, setMsg] = useState('');
  const cur = w && w.current;
  const saved = (w && w.saved) || [];

  const remove = async (slot, ssid) => {
    if (!confirm(t('js_rm_pre') + ssid + t('js_rm_suf'))) return;
    try { setMsg((await apiPost('/api/wifi/remove', { slot })).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    reload();
  };

  return (
    <div class="card">
      <h2><i class="ico ico-list"></i> {t('wifi_saved_head')}</h2>
      <p class="muted">{t('wifi_saved_note')}</p>
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

function AudioOutputCard() {
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
      <button class="btn sec" disabled={testing} onClick={test}>{t('audio_test_btn')}</button>
      {rebootReq && <button class="btn sec" disabled={rebooting} onClick={reboot}>{t('js_reboot')}</button>}
      {out === 'hdmi' && hdmiNoDisp && <p class="muted">{t('audio_hdmi_nodisp')}</p>}
      <p class="muted">
        {rebooting && <span class="spinner"></span>}{' '}
        {msg || (rebootReq ? t('js_audio_reboot') : '')}
      </p>
    </div>
  );
}

function LanguageCard() {
  const { t, lang } = useI18n();
  const change = async (e) => {
    const l = e.currentTarget.value;
    try { await apiPost('/api/lang', { lang: l }); } catch { /* ignore */ }
    location.reload();
  };
  return (
    <div class="card">
      <h2><i class="ico ico-globe"></i> {t('lang_head')}</h2>
      <p class="muted">{t('lang_note')}</p>
      <select value={lang} onChange={change}>
        <option value="en">English</option>
        <option value="pl">Polski</option>
      </select>
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

// Client-only appearance switch: sets data-theme on <html> and remembers it in
// localStorage. Applies live — no reload, no server round-trip.
function ThemeCard() {
  const { t } = useI18n();
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
  const change = (e) => {
    const v = e.currentTarget.value;
    setTheme(v);
    try { localStorage.setItem('theme', v); } catch { /* private mode */ }
    applyTheme(v);
  };
  return (
    <div class="card">
      <h2><i class="ico ico-brush"></i> {t('theme_head')}</h2>
      <p class="muted">{t('theme_note')}</p>
      <select value={theme} onChange={change}>
        <option value="system">{t('theme_system')}</option>
        <option value="mono-light">{t('theme_mono_light')}</option>
        <option value="mono-dark">{t('theme_mono_dark')}</option>
        <option value="neon">{t('theme_neon')}</option>
      </select>
    </div>
  );
}

function UpdateCard() {
  const { t } = useI18n();
  const toast = useToast();
  const [msg, setMsg] = useState('');
  const [checking, setChecking] = useState(false);
  const [running, setRunning] = useState(false);
  const timer = useRef(null);

  const poll = () => {
    if (timer.current) return;
    setRunning(true);
    setMsg(t('js_upd_running'));
    timer.current = setInterval(async () => {
      try {
        const j = await apiGet('/api/update');
        if (j.running) return;
        clearInterval(timer.current);
        timer.current = null;
        setRunning(false);
        if (j.failed) {
          setMsg(t('js_upd_failed'));
        } else {
          setMsg(t('js_upd_done'));
          toast(t('upd_done_toast'));
          setTimeout(() => location.reload(), 1500);
        }
      } catch { /* panel restarting mid-update — keep polling */ }
    }, 3000);
  };

  // page opened while an update is already running -> resume the poll
  useEffect(() => {
    apiGet('/api/update').then((j) => { if (j.running) poll(); }).catch(() => {});
    return () => timer.current && clearInterval(timer.current);
  }, []);

  const check = async () => {
    setChecking(true);
    setMsg(t('js_upd_checking'));
    try {
      const j = await apiGet('/api/update/check');
      setMsg(!j.ok ? t('js_upd_checkfail')
        : (j.update_available ? t('js_upd_available') : t('js_upd_current')));
    } catch { setMsg(t('js_conn_error')); }
    setChecking(false);
  };
  const run = async () => {
    if (!confirm(t('js_upd_confirm'))) return;
    try {
      const j = await apiPost('/api/update/run');
      if (!j.ok) { setMsg(j.message || t('js_error')); return; }
      poll();
    } catch { setMsg(t('js_conn_error')); }
  };

  return (
    <div class="card">
      <h2><i class="ico ico-refresh"></i> {t('upd_head')}</h2>
      <p class="muted">{t('upd_note')}</p>
      <div class="lrow">
        <button class="btn sec" disabled={checking} onClick={check}>{t('upd_check_btn')}</button>
        <button class="btn sec" disabled={running} onClick={run}>{t('upd_run_btn')}</button>
      </div>
      <p class="muted">{running && <span class="spinner"></span>}{' '}{msg}</p>
    </div>
  );
}

// Mirror of UpdateCard for the mobile app itself: check compares the installed
// build's SHA against the latest release's version.json; "update" hands the APK
// URL to the system browser, which downloads it and fires the package installer.
function AppUpdateCard() {
  const { t } = useI18n();
  const [msg, setMsg] = useState('');
  const [checking, setChecking] = useState(false);
  const [avail, setAvail] = useState(false);

  const check = async () => {
    setChecking(true);
    setMsg(t('js_upd_checking'));
    try {
      const r = await fetch(`${VERSION_URL}?_=${Date.now()}`, { cache: 'no-store' });
      if (!r.ok) throw new Error(String(r.status));
      const latest = ((await r.json()).sha || '').slice(0, 7);
      const isNew = !!latest && latest !== APP_SHA_SHORT;
      setAvail(isNew);
      setMsg(isNew ? t('appupd_available') : t('appupd_current'));
    } catch { setMsg(t('js_upd_checkfail')); }
    setChecking(false);
  };
  const run = async () => { try { await Browser.open({ url: APK_URL }); } catch { /* ignore */ } };

  return (
    <div class="card">
      <h2><i class="ico ico-refresh"></i> {t('appupd_head')}</h2>
      <p class="muted">{t('appupd_note')}</p>
      <p class="muted small">{t('appupd_version')}: {APP_SHA_SHORT}</p>
      <div class="lrow">
        <button class="btn sec" disabled={checking} onClick={check}>{t('upd_check_btn')}</button>
        <button class={'btn' + (avail ? '' : ' sec')} onClick={run}>{t('appupd_run_btn')}</button>
      </div>
      {msg && <p class="muted">{msg}</p>}
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
