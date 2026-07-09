// Shared volume row: icon + range + percentage. Controlled — the parent owns
// the value (via useVolumes) and gets live updates through onInput.
export function VolumeSlider({ value, onInput, label }) {
  const v = value == null ? 0 : value;
  return (
    <label class="volrow">
      <i class="ico ico-volume" aria-hidden="true"></i>
      {label && <span class="volrow-label">{label}</span>}
      <input type="range" min="0" max="100" value={v}
             aria-label={label || 'volume'}
             onInput={(e) => onInput(+e.currentTarget.value)} />
      <span class="volrow-pct muted">{v}</span>
    </label>
  );
}
