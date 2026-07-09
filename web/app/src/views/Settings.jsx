import { useState } from 'preact/hooks';
import { useSwipe } from '../hooks.js';
import { useI18n } from '../i18n.jsx';
import { CustomizeSection } from './settings/CustomizeSection.jsx';
import { ConnectionsSection } from './settings/ConnectionsSection.jsx';
import { ConfigSection } from './settings/ConfigSection.jsx';
import { AboutSection } from './settings/AboutSection.jsx';

// The left nav is now a client-side section switch (no hash-scroll, no reload).
// The top-level hash is owned by the router (#/settings), so the active section
// is component state, remembered in localStorage like the old page did.
const SECTIONS = [
  ['customize', 'nav_customize', CustomizeSection],
  ['connections', 'nav_connections', ConnectionsSection],
  ['config', 'nav_config', ConfigSection],
  ['about', 'nav_about', AboutSection],
];

function initialSection() {
  try {
    const saved = localStorage.getItem('settingstab');
    if (saved && SECTIONS.some(([id]) => id === saved)) return saved;
  } catch { /* ignore */ }
  return 'config';
}

export function Settings() {
  const { t } = useI18n();
  const [sec, setSec] = useState(initialSection);

  const pick = (id) => {
    setSec(id);
    try { localStorage.setItem('settingstab', id); } catch { /* ignore */ }
  };
  // swipe left → next section, right → previous; clamped at the ends
  const step = (d) => {
    const ids = SECTIONS.map(([id]) => id);
    const j = ids.indexOf(sec) + d;
    if (j >= 0 && j < ids.length) pick(ids[j]);
  };
  const swipe = useSwipe({ onLeft: () => step(1), onRight: () => step(-1) });

  const Active = (SECTIONS.find(([id]) => id === sec) || SECTIONS[0])[2];

  return (
    <div class="layout" {...swipe}>
      <nav class="snav">
        {SECTIONS.map(([id, key]) => (
          <a key={id} href="javascript:void 0" class={sec === id ? 'active' : ''}
             onClick={(e) => { e.preventDefault(); pick(id); }}>
            {t(key)}
          </a>))}
      </nav>
      <div class="content">
        <Active />
      </div>
    </div>
  );
}
