import { createContext } from 'preact';
import { useContext, useEffect, useState } from 'preact/hooks';
import { IS_APP, apiBase, apiUrl, rememberDevice } from './host.js';

// All translated strings + device config come from /api/i18n in one shot at
// boot. Python's STR dict stays the single source of truth; the bundle carries
// no baked-in copy, which is what keeps it fully static and portable to a
// native shell.

const I18nContext = createContext(null);

const FALLBACK = {
  lang: 'en', langs: ['en'], device: 'Synchrofazotron',
  player: '', lms_port: 9000, pair_win: 180, repo: '', version: '', strings: {},
};

const CACHE_KEY = 'i18n';

export function I18nProvider({ children }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetch(apiUrl('/api/i18n'), { cache: 'no-store' })
      .then((r) => r.json())
      .then((d) => {
        try { localStorage.setItem(CACHE_KEY, JSON.stringify(d)); } catch { /* full/private */ }
        // keep the picker's saved-devices list fresh: every successful boot
        // against a device (re)files it under its current name
        if (IS_APP && apiBase() && d.device) rememberDevice(d.device, apiBase());
        setData(d);
      })
      .catch(() => {
        // no device (picker skipped) or offline — the last device's strings
        // beat FALLBACK's raw keys; FALLBACK only on a truly first run
        try { setData(JSON.parse(localStorage.getItem(CACHE_KEY)) || FALLBACK); }
        catch { setData(FALLBACK); }
      });
  }, []);
  // Theme background is already painted by style.css, so a blank first frame is
  // invisible; this resolves in one request.
  if (!data) return null;
  return <I18nContext.Provider value={data}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const d = useContext(I18nContext) || FALLBACK;
  return {
    t: (key) => (d.strings && d.strings[key]) ?? key,
    lang: d.lang,
    langs: d.langs,
    device: d.device,
    player: d.player,
    lmsPort: d.lms_port,
    pairWin: d.pair_win,
    repo: d.repo,
    version: d.version,
  };
}
