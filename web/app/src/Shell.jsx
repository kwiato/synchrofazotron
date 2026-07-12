import { useEffect, useRef } from 'preact/hooks';
import { useRoute } from './router.jsx';
import { useI18n } from './i18n.jsx';
import { Header } from './components/Header.jsx';
import { PlayerBar } from './components/PlayerBar.jsx';
import { Droplet } from './components/Droplet.jsx';
import { Panel } from './views/Panel.jsx';
import { Settings } from './views/Settings.jsx';
import { useUpdate, updResume } from './update.js';

// Persistent chrome (header + player bar) wraps a single animated view slot.
// Navigation order drives the slide direction.
const ORDER = { '/': 0, '/settings': 1 };

// The system-update droplet is app chrome, not a Settings detail: the run
// keeps going (and the panel restarts) no matter which view is open, so the
// pill has to survive navigation. State lives in update.js.
function UpdateDroplet() {
  const { t } = useI18n();
  const { drop } = useUpdate();
  useEffect(() => { updResume(); }, []);
  if (!drop) return null;
  return (
    <Droplet open={drop.open} text={drop.text || t(drop.key)} tone={drop.tone}
             icon={drop.icon} spinner={drop.spinner} />
  );
}

export function Shell() {
  const path = useRoute();
  const prev = useRef(path);
  const forward = (ORDER[path] ?? 0) >= (ORDER[prev.current] ?? 0);
  useEffect(() => { prev.current = path; }, [path]);

  const View = path === '/settings' ? Settings : Panel;

  return (
    <>
      <div class="wrap-wide">
        <Header />
        <div class="stage">
          <div class={'route route-enter-' + (forward ? 'fwd' : 'back')} key={path}>
            <View />
          </div>
        </div>
      </div>
      <PlayerBar />
      <UpdateDroplet />
    </>
  );
}
