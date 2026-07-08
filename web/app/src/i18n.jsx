import { createContext } from 'preact';
import { useContext, useEffect, useState } from 'preact/hooks';

// All translated strings + device config come from /api/i18n in one shot at
// boot. Python's STR dict stays the single source of truth; the bundle carries
// no baked-in copy, which is what keeps it fully static and portable to a
// native shell.

const I18nContext = createContext(null);

const FALLBACK = {
  lang: 'en', langs: ['en'], device: 'Synchrofazotron',
  player: '', lms_port: 9000, pair_win: 180, repo: '', strings: {},
};

export function I18nProvider({ children }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetch('/api/i18n', { cache: 'no-store' })
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(FALLBACK));
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
  };
}
