import { useState } from 'preact/hooks';

// The Synchrophasotron monitoring ring: four symmetric arcs (gaps at top/right/
// bottom/left) of rectangular segments in two concentric rows. Segments rest at
// the theme ink; now and then one snaps on with the cyberpunk glow (alternating
// cyan/pink) and slowly fades — phases golden-ratio scattered so it reads random.
const ARCS = [45, 135, 225, 315];          // arc centres — gaps at 0/90/180/270
const OFFS = [-32, -16, 0, 16, 32];        // 5 segments per arc → 26° cardinal gaps
const ROWS = [40, 54];                     // inner / outer radius
const CX = 62, CY = 62, W = 6, H = 10, T = 36;

function segments() {
  const segs = [];
  ARCS.forEach((c) => OFFS.forEach((o) => ROWS.forEach((r) => segs.push({ deg: c + o, r }))));
  [...segs].sort((a, b) => a.deg - b.deg).forEach((s, k) => { s.ord = k; });
  segs.forEach((s, i) => {
    s.hot = i % 2 ? '#c26bf5' : '#2dd4ee';
    s.dly = (((i * 0.61803) % 1) * T).toFixed(2);
  });
  return segs;
}

// Presentational SVG ring — used big + flickering in About, and small as the
// header brand mark (where CSS runs only the one-shot power-on, no ambient).
export function RingMark({ class: cls = '' }) {
  return (
    <svg class={'ring-mark' + (cls ? ' ' + cls : '')} viewBox="0 0 124 124" role="img" aria-hidden="true">
      {segments().map((s, i) => (
        <rect key={i} class="seg" x={CX - W / 2} y={CY - s.r - H / 2} width={W} height={H}
              transform={`rotate(${s.deg} ${CX} ${CY})`}
              style={`--hot:${s.hot}; --dly:${s.dly}s; --ord:${s.ord}`} />
      ))}
    </svg>
  );
}

// About logo: clicking power-cycles the ring (remount → the sweep replays).
export function ConsoleLogo() {
  const [gen, setGen] = useState(0);
  return (
    <button type="button" class="ring-logo" onClick={() => setGen((n) => n + 1)}
            aria-label="Synchrofazotron" title="Synchrofazotron">
      <RingMark key={gen} />
    </button>
  );
}
