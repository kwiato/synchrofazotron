import { useEffect, useRef, useState } from 'preact/hooks';
import { RingMark } from '../components/ConsoleLogo.jsx';
import { setApiBase } from '../host.js';
import { startDiscovery } from '../discovery.js';
import { APP_SHA_SHORT } from '../appversion.js';
import { appUpdateAvailable, installAppUpdate } from '../appupdate.js';

// Device picker shown in the app before any device is chosen. It runs *before*
// /api/i18n (there is no device yet to fetch strings from), so it carries its
// own tiny PL/EN dictionary keyed off the phone locale / last saved choice.
const LANG = (() => {
  try { const l = localStorage.getItem('lang'); if (l) return l; } catch { /* */ }
  return (navigator.language || 'en').toLowerCase().startsWith('pl') ? 'pl' : 'en';
})();
const S = {
  en: {
    tag: 'Pick your device', searching: 'Looking for devices on the network…',
    none: 'None found yet. Make sure the phone is on the same Wi-Fi as the device.',
    manual: 'or enter an address', connect: 'Connect', ph: 'e.g. 192.168.1.50',
    checking: 'Connecting…', unreachable: 'Could not reach that device.',
    upd_link: 'Update the app', upd_install: 'Install the update',
    upd_checking: 'Checking…', upd_current: 'The app is up to date.',
    upd_available: 'A newer build is available.',
    upd_checkfail: 'Could not check for updates.',
    upd_allow: 'Allow installing from this app, then tap again.',
    upd_downloading: 'Downloading…',
    upd_installing: 'Downloaded — the installer should open.',
    upd_fail: 'Download failed — opening the browser.',
  },
  pl: {
    tag: 'Wybierz urządzenie', searching: 'Szukam urządzeń w sieci…',
    none: 'Na razie nic nie znaleziono. Upewnij się, że telefon jest w tym samym Wi-Fi co urządzenie.',
    manual: 'albo podaj adres', connect: 'Połącz', ph: 'np. 192.168.1.50',
    checking: 'Łączę…', unreachable: 'Nie udało się połączyć z tym urządzeniem.',
    upd_link: 'Zaktualizuj aplikację', upd_install: 'Zainstaluj aktualizację',
    upd_checking: 'Sprawdzam…', upd_current: 'Aplikacja jest aktualna.',
    upd_available: 'Jest nowsza wersja.',
    upd_checkfail: 'Nie udało się sprawdzić aktualizacji.',
    upd_allow: 'Zezwól na instalację z tej aplikacji i kliknij ponownie.',
    upd_downloading: 'Pobieram…',
    upd_installing: 'Pobrane — powinien otworzyć się instalator.',
    upd_fail: 'Pobieranie nie wyszło — otwieram przeglądarkę.',
  },
}[LANG];

// A device answers on /api/i18n; use it to validate a pick before committing.
async function reachable(url) {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 4000);
    const r = await fetch(`${url}/api/i18n`, { cache: 'no-store', signal: ctrl.signal });
    clearTimeout(timer);
    return r.ok;
  } catch { return false; }
}

export function Connect({ onConnect }) {
  const [devices, setDevices] = useState([]);
  const [manual, setManual] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const stopRef = useRef(null);

  useEffect(() => {
    let live = true;
    startDiscovery((list) => { if (live) setDevices(list); })
      .then((stop) => { stopRef.current = stop; })
      .catch(() => { /* not on a native platform / no permission */ });
    return () => { live = false; if (stopRef.current) stopRef.current(); };
  }, []);

  const pick = async (url) => {
    setErr(''); setBusy(true);
    if (await reachable(url)) {
      if (stopRef.current) await stopRef.current();
      setApiBase(url);
      onConnect();
    } else {
      setErr(S.unreachable);
      setBusy(false);
    }
  };

  const pickManual = () => {
    const v = manual.trim();
    if (!v) return;
    const url = /^https?:\/\//.test(v) ? v : `http://${v}${/:\d+$/.test(v) ? '' : ':8787'}`;
    pick(url);
  };

  return (
    <div class="wrap-wide connect">
      <div class="connect-brand"><RingMark class="brand-mark" /></div>
      <p class="connect-tag">{S.tag}</p>

      <div class="card">
        {devices.length === 0 && (
          <div class="empty">
            <i class="ico empty-ico ico-wifi"></i>
            <p class="empty-title">{S.searching}</p>
            <p class="empty-sub">{S.none}</p>
          </div>
        )}
        {devices.map((d) => (
          <button key={d.name} class="device-row" disabled={busy} onClick={() => pick(d.url)}>
            <span class="device-name">{d.name}</span>
            <span class="device-addr muted">{d.ip}:{d.port}</span>
          </button>
        ))}
      </div>

      <p class="muted connect-manual-label">{S.manual}</p>
      <div class="connect-manual">
        <input class="in" type="text" inputMode="url" placeholder={S.ph}
               value={manual} disabled={busy}
               onInput={(e) => setManual(e.currentTarget.value)}
               onKeyDown={(e) => { if (e.key === 'Enter') pickManual(); }} />
        <button class="btn" disabled={busy || !manual.trim()} onClick={pickManual}>
          {busy ? S.checking : S.connect}
        </button>
      </div>
      {err && <p class="connect-err">{err}</p>}
      <AppUpdate />
    </div>
  );
}

// Escape hatch: the updater normally lives in Settings, which needs a
// connected device — unreachable exactly when a broken build blocks
// connecting. First tap checks; a second tap installs when a build is newer.
function AppUpdate() {
  const [msg, setMsg] = useState('');
  const [avail, setAvail] = useState(false);
  const [busy, setBusy] = useState(false);

  const check = async () => {
    setBusy(true); setAvail(false); setMsg(S.upd_checking);
    const a = await appUpdateAvailable();
    setAvail(!!a);
    setMsg(a == null ? S.upd_checkfail : a ? S.upd_available : S.upd_current);
    setBusy(false);
  };
  const install = async () => {
    setBusy(true);
    await installAppUpdate((state, pct) => {
      if (state === 'allow') setMsg(S.upd_allow);
      else if (state === 'downloading') setMsg(S.upd_downloading + (pct != null ? ` ${pct}%` : ''));
      else if (state === 'installing') setMsg(S.upd_installing);
      else setMsg(S.upd_fail);
    });
    setBusy(false);
  };

  return (
    <div class="connect-upd">
      <button class="connect-updbtn muted" disabled={busy} onClick={avail ? install : check}>
        {avail ? S.upd_install : S.upd_link} · {APP_SHA_SHORT}
      </button>
      {msg && <p class="muted small connect-updmsg">{msg}</p>}
    </div>
  );
}
