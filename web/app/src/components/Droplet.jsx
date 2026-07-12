import { useEffect, useLayoutEffect, useRef, useState } from 'preact/hooks';

// Morphing notification bubble. A neutral dot expands sideways into a pill to
// reveal its content, takes on its tone colour only near the end, then (when
// `open` goes false) collapses in place and merges away leaving a ripple.
// Controlled: `open` drives the morph and the content props update live, so a
// spinner can resolve into a check. Long text wraps: the pill caps its width
// and grows down — sideways first, then taller. `inline` renders inside a slot
// div that reserves the height with a quick grow, then the droplet morphs in
// its centre; otherwise it's pinned centered at the top. `timeout` (ms) auto-
// hides a resolved (non-spinner) state; any content change re-opens it.
// Styles: ui/style.scss.

const ICONS = {
  check: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path class="draw" d="M4 12.5 L10 18 L20 6"/></svg>',
  x:     '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path class="draw" d="M6 6 L18 18 M18 6 L6 18"/></svg>',
  dot:   '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path class="draw" d="M12 6 L12 14 M12 18 L12 18.01"/></svg>',
};
const TONE_VAR = { good: '--good', warn: '--warn', danger: '--danger' };
const H = 42;          // single-line pill height — keep in sync with style.scss
const MAXW = 420;      // widest the pill goes before the text wraps

// let the pill size to its content, read it, then restore — so it morphs to
// fit. Past maxW the text wraps and the measured height grows instead.
function measure(el, box) {
  const s = el.style;
  const prev = { w: s.width, h: s.height, t: s.transition, o: s.overflow,
                 r: s.right, b: s.bottom };
  s.transition = 'none'; s.width = 'auto'; s.height = 'auto'; s.overflow = 'visible';
  // the inline pill is absolutely positioned with inset:0, where width:auto
  // stretches — drop the far offsets so it shrinks to its content instead
  s.right = 'auto'; s.bottom = 'auto';
  el.classList.remove('multi');
  const maxW = Math.min(MAXW, box || Math.round(window.innerWidth * 0.9));
  let w = el.scrollWidth, h = H, multi = false;
  if (w > maxW) {
    multi = true;
    el.classList.add('multi');
    s.width = maxW + 'px';
    w = maxW;
    h = Math.max(H, el.scrollHeight);
  }
  s.width = prev.w; s.height = prev.h; s.transition = prev.t; s.overflow = prev.o;
  s.right = prev.r; s.bottom = prev.b;
  return { w, h, multi };
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

export function Droplet({ open, text, tone, icon = 'check', spinner = false,
                          inline = false, timeout = 0 }) {
  const elRef = useRef(null);
  const slotRef = useRef(null);
  const iconRef = useRef(null);
  const textRef = useRef(null);
  const opened = useRef(false);
  const timers = useRef([]);

  // auto-hide a settled state after `timeout`; new content re-arms and re-opens
  const [expired, setExpired] = useState(false);
  useEffect(() => { setExpired(false); }, [open, text, tone, icon, spinner]);
  useEffect(() => {
    if (!timeout || !open || spinner) return undefined;
    const id = setTimeout(() => setExpired(true), timeout);
    return () => clearTimeout(id);
  }, [timeout, open, spinner, text, tone, icon]);
  const shown = open && !expired;

  const maxBox = () => (slotRef.current ? slotRef.current.clientWidth : 0);

  // reflect content before paint; if already open, re-measure so the size
  // animates to fit (e.g. a spinner "Updating…" resolving to "Done")
  useLayoutEffect(() => {
    const el = elRef.current;
    if (!el) return;
    textRef.current.textContent = text || '';
    iconRef.current.innerHTML = ICONS[icon] || ICONS.check;
    el.dataset.tone = tone || '';
    el.classList.toggle('spin', !!spinner);
    if (el.classList.contains('open')) {
      const m = measure(el, maxBox());
      el.style.setProperty('--droplet-w', m.w + 'px');
      el.style.setProperty('--droplet-h', m.h + 'px');
      if (slotRef.current) slotRef.current.style.setProperty('--slot-h', m.h + 'px');
    }
  }, [text, icon, tone, spinner]);

  useEffect(() => {
    const el = elRef.current;
    if (!el) return;
    timers.current.forEach(clearTimeout);
    timers.current = [];
    const slot = slotRef.current;
    if (shown && !opened.current) {
      opened.current = true;
      el.classList.remove('leaving', 'sinking');
      const m = measure(el, maxBox());
      el.style.setProperty('--droplet-w', m.w + 'px');
      el.style.setProperty('--droplet-h', H + 'px');          // sideways first…
      if (m.multi) {
        timers.current.push(setTimeout(() =>
          el.style.setProperty('--droplet-h', m.h + 'px'), 420));  // …then down
      }
      const morph = () => {
        el.classList.add('active');
        void el.offsetWidth;
        requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('open')));
      };
      if (slot) {
        slot.style.setProperty('--slot-h', m.h + 'px');
        slot.classList.add('grown');                 // reserve the space…
        timers.current.push(setTimeout(morph, 200)); // …then morph in its centre
      } else {
        morph();
      }
    } else if (!shown && opened.current) {
      opened.current = false;
      el.classList.remove('open');
      el.classList.add('leaving');                 // collapse to a coloured dot, in place
      timers.current.push(setTimeout(() => {
        spawnRipple(el, el.dataset.tone);           // merge + ripple
        el.classList.add('sinking');
        timers.current.push(setTimeout(() => {
          el.classList.remove('active', 'leaving', 'sinking', 'multi');
          if (slot) slot.classList.remove('grown');
        }, 520));
      }, 300));
    }
  }, [shown]);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const pill = (
    <div class={'droplet' + (inline ? ' droplet-inline' : '')} ref={elRef} data-tone={tone || ''}>
      <div class="droplet-inner">
        <span class="droplet-spin"><span class="spinner"></span></span>
        <span class="droplet-icon" ref={iconRef}></span>
        <span class="droplet-text" ref={textRef}></span>
      </div>
    </div>
  );
  return inline ? <div class="droplet-slot" ref={slotRef}>{pill}</div> : pill;
}
