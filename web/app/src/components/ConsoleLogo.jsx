import { useState } from 'preact/hooks';

// A little Synchrophasotron-style control console: two swaying analog gauges and
// a grid of indicator lamps that flicker on their own. Clicking it "power-cycles"
// the panel (remount via key → the light-up sweep replays). The lamp colours are
// fixed hex (cyberpunk + status palette) so they stay lit in the mono themes too;
// the panel/gauges are drawn in the theme's muted ink.
const PALETTE = ['#34d399', '#2dd4ee', '#fbbf24', '#c26bf5', '#f87171', '#2dd4ee'];
const COLS = [104, 130, 156, 182, 208, 234];
const ROWS = [26, 48];

export function ConsoleLogo() {
  const [gen, setGen] = useState(0);   // bump to replay the power-up sweep

  const lamps = [];
  let i = 0;
  ROWS.forEach((cy) => COLS.forEach((cx, c) => {
    lamps.push({
      cx, cy, col: c, color: PALETTE[i % PALETTE.length],
      d: ((i * 0.19) % 1.3).toFixed(2), t: (1.1 + (i % 4) * 0.35).toFixed(2),
    });
    i += 1;
  }));

  return (
    <button type="button" class="console-logo" onClick={() => setGen((n) => n + 1)}
            aria-label="Synchrofazotron" title="Synchrofazotron">
      <svg key={gen} viewBox="0 0 260 72" role="img" aria-hidden="true">
        <rect class="cl-panel" x="2" y="2" width="256" height="68" rx="9" />
        <g class="cl-gauge">
          <circle cx="34" cy="28" r="13" />
          <line class="cl-needle" x1="34" y1="28" x2="34" y2="17" />
        </g>
        <g class="cl-gauge">
          <circle cx="62" cy="48" r="12" />
          <line class="cl-needle" x1="62" y1="48" x2="62" y2="38" style="animation-delay:-2.4s" />
        </g>
        {lamps.map((l) => (
          <circle key={`${l.cx}-${l.cy}`} class="cl-lamp" cx={l.cx} cy={l.cy} r="5"
                  fill={l.color} style={`--col:${l.col}; --d:${l.d}s; --t:${l.t}s`} />
        ))}
      </svg>
    </button>
  );
}
