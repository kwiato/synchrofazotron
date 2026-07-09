import { createContext } from 'preact';
import { useCallback, useContext, useEffect, useRef } from 'preact/hooks';

// Dynamic-Island-style alert, hoisted to the app root so any view can fire one
// with useIsland(). The lifecycle is DOM-driven (class toggles + a measured
// width) rather than reactive state — the island subtree has no bindings, so
// Preact won't fight the imperative animation. Styles live in ui/style.scss.
const IslandContext = createContext(() => {});

const TONE_VAR = { good: '--good', warn: '--warn', danger: '--danger' };

const ICONS = {
  check: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path class="draw" d="M4 12.5 L10 18 L20 6"/></svg>',
  x:     '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path class="draw" d="M6 6 L18 18 M18 6 L6 18"/></svg>',
  dot:   '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path class="draw" d="M12 6 L12 14 M12 18 L12 18.01"/></svg>',
};

// let the pill size to its content, read it, then restore — so it morphs to fit
function measure(el) {
  const w0 = el.style.width, t0 = el.style.transition, o0 = el.style.overflow;
  el.style.transition = 'none'; el.style.width = 'auto'; el.style.overflow = 'visible';
  const w = Math.min(el.scrollWidth, Math.round(window.innerWidth * 0.9));
  el.style.width = w0; el.style.transition = t0; el.style.overflow = o0;
  return w;
}

function spawnRipple(tone) {
  const r = document.createElement('div');
  r.className = 'island-ripple';
  r.style.borderColor = `var(${TONE_VAR[tone] || '--text'})`;
  document.body.appendChild(r);
  r.addEventListener('animationend', () => r.remove());
}

export function IslandProvider({ children }) {
  const elRef = useRef(null);
  const iconRef = useRef(null);
  const textRef = useRef(null);
  const timers = useRef([]);

  const island = useCallback(({ text, tone = 'good', icon = 'check', hold = 2000 }) => {
    const el = elRef.current;
    if (!el) return;
    timers.current.forEach(clearTimeout);
    timers.current = [];

    el.classList.remove('open', 'leaving', 'sinking');
    el.dataset.tone = tone;
    textRef.current.textContent = text;
    iconRef.current.innerHTML = ICONS[icon] || ICONS.check;

    el.classList.add('active');            // neutral dot
    void el.offsetWidth;                   // flush before measuring/opening
    el.style.setProperty('--island-w', measure(el) + 'px');
    requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('open')));

    timers.current.push(setTimeout(() => {
      el.classList.remove('open');
      el.classList.add('leaving');         // collapse to a coloured dot, in place
      timers.current.push(setTimeout(() => {
        spawnRipple(el.dataset.tone);      // merge + ripple
        el.classList.add('sinking');
        timers.current.push(setTimeout(() => {
          el.classList.remove('active', 'leaving', 'sinking');
        }, 520));
      }, 300));
    }, hold));
  }, []);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  return (
    <IslandContext.Provider value={island}>
      {children}
      <div class="island" ref={elRef} data-tone="good">
        <div class="island-inner">
          <span class="island-icon" ref={iconRef}></span>
          <span class="island-text" ref={textRef}></span>
        </div>
      </div>
    </IslandContext.Provider>
  );
}

export const useIsland = () => useContext(IslandContext);
