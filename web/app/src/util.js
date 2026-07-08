// Source-selection helpers, ported verbatim from the old common.js so behaviour
// matches the current panel exactly.

/* the source the player bar (and the main page) follows: first playing one,
   otherwise the first known (paused/connected) one */
export function primary(status) {
  const src = (status && status.sources) || [];
  return src.find((x) => x.playing) || src[0] || null;
}

/* subtitle under the track name: artist (LMS only) + source + state */
export function srcSub(p) {
  const bits = [];
  if (p.artist) bits.push(p.artist);
  bits.push(p.detail ? `${p.name} — ${p.state}` : p.state);
  return bits.join(' · ');
}
