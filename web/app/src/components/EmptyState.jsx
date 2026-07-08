// Centered placeholder for an empty / unavailable state: a large icon over a
// light-weight title and optional sub-line. Used e.g. when there is no HDMI
// monitor to show the visualizer on.
export function EmptyState({ icon, title, sub }) {
  return (
    <div class="empty">
      {icon && <i class={'ico empty-ico ' + icon}></i>}
      <p class="empty-title">{title}</p>
      {sub && <p class="empty-sub">{sub}</p>}
    </div>
  );
}
