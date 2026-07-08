import { useState } from 'preact/hooks';
import { useI18n } from '../i18n.jsx';
import { ConfigSection } from './settings/ConfigSection.jsx';
import { SourcesSection } from './settings/SourcesSection.jsx';
import { VisualizerSection } from './settings/VisualizerSection.jsx';
import { AboutSection } from './settings/AboutSection.jsx';

// The left nav is now a client-side section switch (no hash-scroll, no reload).
// The top-level hash is owned by the router (#/settings), so the active section
// is component state, remembered in localStorage like the old page did.
const SECTIONS = [
  ['config', 'nav_config', ConfigSection],
  ['sources', 'nav_sources', SourcesSection],
  ['visualizer', 'nav_viz', VisualizerSection],
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

  const Active = (SECTIONS.find(([id]) => id === sec) || SECTIONS[0])[2];

  return (
    <div class="layout">
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
