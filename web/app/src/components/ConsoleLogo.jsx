import { useState } from 'preact/hooks';

// The Synchrophasotron monitoring ring: four symmetric arcs (gaps at top, right,
// bottom, left) of rectangular segments, in two concentric rows. Segments rest
// at the theme ink (black on light, white on dark/neon); now and then one snaps
// on with the cyberpunk glow (alternating cyan/pink) and slowly fades — phases
// scattered by the golden ratio so it reads as random, not a sweep. On mount /
// click the whole ring lights up once in angular order (power-on).
const ARCS = [45, 135, 225, 315];          // arc centres — gaps sit at 0/90/180/270
const OFFS = [-32, -16, 0, 16, 32];        // 5 segments per arc → 26° cardinal gaps
const ROWS = [40, 54];                     // inner / outer radius
const CX = 62, CY = 62, W = 4, H = 10, T = 36;

export function ConsoleLogo() {
  const [gen, setGen] = useState(0);       // bump → remount → replay the sweep

  const segs = [];
  ARCS.forEach((c) => OFFS.forEach((o) => ROWS.forEach((r) => {
    segs.push({ deg: c + o, r });
  })));
  // intro sweep goes round by angle
  [...segs].sort((a, b) => a.deg - b.deg).forEach((s, k) => { s.ord = k; });
  segs.forEach((s, i) => {
    s.hot = i % 2 ? '#c26bf5' : '#2dd4ee';
    s.dly = (((i * 0.61803) % 1) * T).toFixed(2);
  });

  return (
    <button type="button" class="ring-logo" onClick={() => setGen((n) => n + 1)}
            aria-label="Synchrofazotron" title="Synchrofazotron">
      <svg key={gen} viewBox="0 0 124 124" role="img" aria-hidden="true">
        {segs.map((s, i) => (
          <rect key={i} class="seg" x={CX - W / 2} y={CY - s.r - H / 2}
                width={W} height={H}
                transform={`rotate(${s.deg} ${CX} ${CY})`}
                style={`--hot:${s.hot}; --dly:${s.dly}s; --ord:${s.ord}`} />
        ))}
      </svg>
    </button>
  );
}
