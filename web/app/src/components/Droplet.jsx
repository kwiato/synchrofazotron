import { useEffect, useLayoutEffect, useRef } from 'preact/hooks';

// Morphing notification bubble. A neutral dot expands sideways into a pill to
// reveal its content, takes on its tone colour only near the end, then (when
// `open` goes false) collapses in place and merges away leaving a ripple.
// Controlled: `open` drives the morph and the content props update live, so a
// spinner can resolve into a check. `inline` flows it in the DOM (under whatever
// rendered it); otherwise it's pinned centered at the top. Styles: ui/style.scss.

const ICONS = {
  check: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path class="draw" d="M4 12.5 L10 18 L20 6"/></svg>',
  x:     '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path class="draw" d="M6 6 L18 18 M18 6 L6 18"/></svg>',
  dot:   '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path class="draw" d="M12 6 L12 14 M12 18 L12 18.01"/></svg>',
};
const TONE_VAR = { good: '--good', warn: '--warn', danger: '--danger' };

// let the pill size to its content, read it, then restore — so it morphs to fit
function measure(el) {
  const w0 = el.style.width, t0 = el.style.transition, o0 = el.style.overflow;
  el.style.transition = 'none'; el.style.width = 'auto'; el.style.overflow = 'visible';
  const w = Math.min(el.scrollWidth, Math.round(window.innerWidth * 0.9));
  el.style.width = w0; el.style.transition = t0; el.style.overflow = o0;
  return w;
}

// a fading ring, centered on the droplet's current on-screen position
function spawnRipple(el, tone) {
  const r = el.getBoundingClientRect();
  const ring = document.createElement('div');
  ring.className = 'droplet-ripple';
  ring.style.left = (r.left + r.width / 2) + 'px';
  ring.style.top = (r.top + r.height / 2) + 'px';
  ring.style.borderColor = `var(${TONE_VAR[tone] || '--text'})`;
  document.body.appendChild(ring);
  ring.addEventListener('animationend', () => ring.remove());
}

export function Droplet({ open, text, tone, icon = 'check', spinner = false, inline = false }) {
  const elRef = useRef(null);
  const iconRef = useRef(null);
  const textRef = useRef(null);
  const opened = useRef(false);
  const timers = useRef([]);

  // reflect content before paint; if already open, re-measure so the width
  // animates to fit (e.g. a spinner "Updating…" resolving to "Done ✓")
  useLayoutEffect(() => {
    const el = elRef.current;
    if (!el) return;
    textRef.current.textContent = text || '';
    iconRef.current.innerHTML = ICONS[icon] || ICONS.check;
    el.dataset.tone = tone || '';
    el.classList.toggle('spin', !!spinner);
    if (el.classList.contains('open')) el.style.setProperty('--droplet-w', measure(el) + 'px');
  }, [text, icon, tone, spinner]);

  useEffect(() => {
    const el = elRef.current;
    if (!el) return;
    timers.current.forEach(clearTimeout);
    timers.current = [];
    if (open && !opened.current) {
      opened.current = true;
      el.classList.remove('leaving', 'sinking');
      el.classList.add('active');
      void el.offsetWidth;
      el.style.setProperty('--droplet-w', measure(el) + 'px');
      requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('open')));
    } else if (!open && opened.current) {
      opened.current = false;
      el.classList.remove('open');
      el.classList.add('leaving');                 // collapse to a coloured dot, in place
      timers.current.push(setTimeout(() => {
        spawnRipple(el, el.dataset.tone);           // merge + ripple
        el.classList.add('sinking');
        timers.current.push(setTimeout(() => el.classList.remove('active', 'leaving', 'sinking'), 520));
      }, 300));
    }
  }, [open]);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  return (
    <div class={'droplet' + (inline ? ' droplet-inline' : '')} ref={elRef} data-tone={tone || ''}>
      <div class="droplet-inner">
        <span class="droplet-spin"><span class="spinner"></span></span>
        <span class="droplet-icon" ref={iconRef}></span>
        <span class="droplet-text" ref={textRef}></span>
      </div>
    </div>
  );
}
