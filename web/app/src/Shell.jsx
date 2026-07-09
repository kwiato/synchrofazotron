import { useEffect, useRef } from 'preact/hooks';
import { useRoute } from './router.jsx';
import { Header } from './components/Header.jsx';
import { PlayerBar } from './components/PlayerBar.jsx';
import { PullSheet } from './components/PullSheet.jsx';
import { Panel } from './views/Panel.jsx';
import { Settings } from './views/Settings.jsx';

// Persistent chrome (header + player bar) wraps a single animated view slot.
// Navigation order drives the slide direction.
const ORDER = { '/': 0, '/settings': 1 };

export function Shell() {
  const path = useRoute();
  const prev = useRef(path);
  const forward = (ORDER[path] ?? 0) >= (ORDER[prev.current] ?? 0);
  useEffect(() => { prev.current = path; }, [path]);

  const View = path === '/settings' ? Settings : Panel;

  return (
    <>
      <PullSheet>
        <div class="wrap-wide">
          <Header />
          <div class="stage">
            <div class={'route route-enter-' + (forward ? 'fwd' : 'back')} key={path}>
              <View />
            </div>
          </div>
        </div>
      </PullSheet>
      <PlayerBar />
    </>
  );
}
