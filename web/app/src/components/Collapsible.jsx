// Reusable collapse: animates its content open/closed with the grid 0fr↔1fr
// trick (height-agnostic, no JS measuring, GPU-friendly). When closed it takes
// no space and is hidden from the a11y tree. Used to fold away controls that
// only matter when a feature is on (e.g. the visualizer options).
export function Collapsible({ open, children }) {
  return (
    <div class={'collapsible' + (open ? ' open' : '')} aria-hidden={open ? undefined : 'true'}>
      <div class="collapsible-in">{children}</div>
    </div>
  );
}
