// The animated equalizer glyph, reused in the header art, player bar and source
// rows. Same markup/classes as the old panel so style.css styles it unchanged.
export function Eq({ n = 3, on = false }) {
  const bars = [];
  for (let i = 0; i < n; i++) bars.push(<i key={i} />);
  return <span class={'eq' + (on ? '' : ' off')}>{bars}</span>;
}
