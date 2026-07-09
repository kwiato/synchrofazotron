import { useEffect, useRef, useState } from 'preact/hooks';
import { StatusTray } from './StatusTray.jsx';

// Pull-to-reveal status shade. The app sheet (header + view) sits on a darker
// backdrop; dragging it down from the top uncovers a fixed status tray behind
// it. Past a threshold the release latches it open (so you can read it); the
// next touch closes it. Touch-only — a no-op with a mouse / on desktop.
const MAX = 128;      // tray height and the resting open offset (px)
const THRESH = 60;    // release past this latches open

// Rubber-band once past MAX so it never feels unbounded.
const resist = (dy) => (dy <= MAX ? dy : MAX + (dy - MAX) * 0.35);

export function PullSheet({ children }) {
  const [open, setOpen] = useState(false);
  const [drag, setDrag] = useState(null);   // px during an active pull, else null
  const rootRef = useRef(null);
  const startY = useRef(0);
  const activeRef = useRef(false);
  const dragRef = useRef(null);
  const openRef = useRef(false);

  const setDragBoth = (v) => { dragRef.current = v; setDrag(v); };
  openRef.current = open;

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return undefined;

    const onStart = (e) => {
      // A touch while open just closes it; otherwise a pull only arms at the top.
      if (openRef.current) { setOpen(false); activeRef.current = false; return; }
      if (window.scrollY > 0) { activeRef.current = false; return; }
      startY.current = e.touches[0].clientY;
      activeRef.current = true;
    };
    const onMove = (e) => {
      if (!activeRef.current) return;
      const dy = e.touches[0].clientY - startY.current;
      if (dy <= 0) { setDragBoth(0); return; }          // pulling back up
      if (window.scrollY > 0) { activeRef.current = false; setDragBoth(null); return; }
      e.preventDefault();                                // take over from scrolling
      setDragBoth(resist(dy));
    };
    const onEnd = () => {
      if (!activeRef.current) return;
      activeRef.current = false;
      setOpen(dragRef.current != null && dragRef.current > THRESH);
      setDragBoth(null);
    };

    el.addEventListener('touchstart', onStart, { passive: true });
    el.addEventListener('touchmove', onMove, { passive: false });
    el.addEventListener('touchend', onEnd, { passive: true });
    el.addEventListener('touchcancel', onEnd, { passive: true });
    return () => {
      el.removeEventListener('touchstart', onStart);
      el.removeEventListener('touchmove', onMove);
      el.removeEventListener('touchend', onEnd);
      el.removeEventListener('touchcancel', onEnd);
    };
  }, []);

  const offset = drag != null ? drag : (open ? MAX : 0);

  return (
    <div class="pullroot" ref={rootRef}>
      <div class="pulltray" aria-hidden={offset === 0}><StatusTray /></div>
      <div class={'pullsheet' + (drag != null ? ' dragging' : '')}
           style={`transform:translateY(${offset}px)`}>
        {children}
      </div>
    </div>
  );
}
