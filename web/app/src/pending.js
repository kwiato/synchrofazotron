// Shared "the device is switching" flag: any transport action (play/pause,
// prev/next, playing a station) turns it on, and the PlayerBar clears it when
// the polled status actually reflects a change — so the user always gets
// feedback between tapping and hearing the result. A 12 s timer clears it on
// its own in case the action silently went nowhere.
import { useEffect, useReducer } from 'preact/hooks';

let on = false;
let timer = null;
const subs = new Set();
const notify = () => subs.forEach((f) => f());

export function pendingStart() {
  on = true;
  clearTimeout(timer);
  timer = setTimeout(pendingClear, 12000);
  notify();
}

export function pendingClear() {
  if (!on) return;
  on = false;
  clearTimeout(timer);
  notify();
}

export function usePending() {
  const [, force] = useReducer((x) => x + 1, 0);
  useEffect(() => { subs.add(force); return () => subs.delete(force); }, []);
  return on;
}
