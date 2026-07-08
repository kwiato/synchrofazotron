// Segmented pill control (shared .tabs/.tab styling). One item is active at a
// time. Used for the Now/Viz switch and the visualizer engine picker, where it
// reads as a mode selector distinct from the action buttons below it.
export function Tabs({ items, active, onChange, compact }) {
  return (
    <nav class={'tabs' + (compact ? ' compact' : '')}>
      {items.map((it) => (
        <button key={it.id} type="button"
                class={'tab' + (it.id === active ? ' active' : '')}
                title={it.title || ''}
                onClick={() => onChange(it.id)}>
          {it.label}
        </button>
      ))}
    </nav>
  );
}
