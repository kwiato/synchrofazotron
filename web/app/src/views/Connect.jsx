import { useEffect, useRef, useState } from 'preact/hooks';
import { RingMark } from '../components/ConsoleLogo.jsx';
import { setApiBase, knownDevices, rememberDevice, forgetDevice } from '../host.js';
import { startDiscovery } from '../discovery.js';

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
    skip: 'Skip — browse without a device',
    saved: 'Saved devices', remove: 'Remove from the list',
  },
  pl: {
    tag: 'Wybierz urządzenie', searching: 'Szukam urządzeń w sieci…',
    none: 'Na razie nic nie znaleziono. Upewnij się, że telefon jest w tym samym Wi-Fi co urządzenie.',
    manual: 'albo podaj adres', connect: 'Połącz', ph: 'np. 192.168.1.50',
    checking: 'Łączę…', unreachable: 'Nie udało się połączyć z tym urządzeniem.',
    skip: 'Pomiń — przeglądaj bez urządzenia',
    saved: 'Zapamiętane urządzenia', remove: 'Usuń z listy',
  },
}[LANG];

// A device answers on /api/i18n; probe it to validate a pick before
// committing. Returns the payload (its .device is the display name used for
// the saved-devices list) or null when unreachable.
async function probe(url) {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 4000);
    const r = await fetch(`${url}/api/i18n`, { cache: 'no-store', signal: ctrl.signal });
    clearTimeout(timer);
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

export function Connect({ onConnect, onSkip }) {
  const [devices, setDevices] = useState([]);
  const [known, setKnown] = useState(knownDevices());
  const [manual, setManual] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const stopRef = useRef(null);
  const forget = (url) => { forgetDevice(url); setKnown(knownDevices()); };
  // a discovered device already on the saved list would render twice
  const discovered = devices.filter((d) => !known.some((k) => k.url === d.url));

  useEffect(() => {
    let live = true;
    startDiscovery((list) => { if (live) setDevices(list); })
      .then((stop) => { stopRef.current = stop; })
      .catch(() => { /* not on a native platform / no permission */ });
    return () => { live = false; if (stopRef.current) stopRef.current(); };
  }, []);

  const pick = async (url) => {
    setErr(''); setBusy(true);
    const info = await probe(url);
    if (info) {
      rememberDevice(info.device || url.replace(/^https?:\/\//, ''), url);
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

      {known.length > 0 && (
        <div class="card">
          <p class="known-head muted">{S.saved}</p>
          {known.map((d) => (
            <div class="known-row" key={d.url}>
              <button class="device-row" disabled={busy} onClick={() => pick(d.url)}>
                <span class="device-name">{d.name}</span>
                <span class="device-addr muted">{d.url.replace(/^https?:\/\//, '')}</span>
              </button>
              <button class="xbtn" title={S.remove} aria-label={S.remove}
                      onClick={() => forget(d.url)}>✕</button>
            </div>
          ))}
        </div>
      )}

      <div class="card">
        {discovered.length === 0 && (
          <div class="empty">
            <i class="ico empty-ico ico-wifi"></i>
            <p class="empty-title">{S.searching}</p>
            <p class="empty-sub">{S.none}</p>
          </div>
        )}
        {discovered.map((d) => (
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
      {/* escape hatch into the UI with no device — device-backed views show
          their empty/error states, but Settings (app update, theme) works */}
      <div class="connect-skip">
        <button class="connect-skipbtn muted" onClick={onSkip}>{S.skip}</button>
      </div>
    </div>
  );
}
