import { useState } from 'preact/hooks';

// The Synchrophasotron monitoring ring: uniform rectangular segments arranged
// around a circle with a gap at the bottom (an open ring). Segments rest dim;
// now and then one snaps on with the cyberpunk glow and slowly fades. On mount
// (and on click → remount) they light up once in a ring sweep, then settle into
// the sporadic ambient flicker. Flash colours alternate cyan/pink (the primary);
// the resting colour is the theme's idle tone, so it works in every theme.
const N = 25;                 // segments
const START = -150;           // first segment angle (0 = top)
const SPAN = 300;             // covered arc → 60° gap at the bottom
const CX = 70, CY = 62, R = 46, W = 5, H = 15;

export function ConsoleLogo() {
  const [gen, setGen] = useState(0);   // bump → remount → replay the sweep
  const step = SPAN / (N - 1);
  const segs = [];
  for (let i = 0; i < N; i += 1) {
    segs.push({
      deg: START + i * step,
      hot: i % 2 ? '#c26bf5' : '#2dd4ee',       // pink / cyan
      dly: (((i * 0.61803) % 1) * 24).toFixed(2), // golden-scattered ambient phase
      ord: i,
    });
  }
  return (
    <button type="button" class="ring-logo" onClick={() => setGen((n) => n + 1)}
            aria-label="Synchrofazotron" title="Synchrofazotron">
      <svg key={gen} viewBox="0 0 140 124" role="img" aria-hidden="true">
        {segs.map((s) => (
          <rect key={s.ord} class="seg" x={CX - W / 2} y={CY - R - H / 2}
                width={W} height={H}
                transform={`rotate(${s.deg} ${CX} ${CY})`}
                style={`--hot:${s.hot}; --dly:${s.dly}s; --ord:${s.ord}`} />
        ))}
      </svg>
    </button>
  );
}
