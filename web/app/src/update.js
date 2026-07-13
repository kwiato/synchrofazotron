// Global "system update in progress" state. The run outlives whatever view
// started it (the panel restarts mid-update), so the poll and the droplet
// data live here; Shell renders the droplet, making it visible everywhere.
// Texts are stored as i18n keys where possible and translated at render time.
import { useEffect, useReducer } from 'preact/hooks';
import { apiGet } from './api.js';

let drop = null;         // {open, key?, text?, tone, icon, spinner}
let polling = null;
let timers = [];
const subs = new Set();
const notify = () => subs.forEach((f) => f());

const set = (d) => { drop = d; notify(); };
const clearTimers = () => { timers.forEach(clearTimeout); timers = []; };
const closeLater = (closeMs, reloadMs) => {
  timers.push(setTimeout(() => { if (drop) set({ ...drop, open: false }); }, closeMs));
  if (reloadMs) timers.push(setTimeout(() => location.reload(), reloadMs));
};

// a run that could not start (API said no / connection refused)
export function updError(text) {
  clearTimers();
  set({ open: true, text, tone: 'danger', icon: 'x', spinner: false });
  closeLater(2400);
}

// The pinned droplet doubles as the generic "system is busy" pill — reboot
// uses these two directly (spinner while down, check + optional reload after).
export function dropSpin(key) {
  clearTimers();
  set({ open: true, key, tone: '', icon: 'check', spinner: true });
}

export function dropDone(key, { tone = 'good', reloadMs = 0 } = {}) {
  clearTimers();
  set({ open: true, key, tone, icon: tone === 'danger' ? 'x' : 'check', spinner: false });
  closeLater(1300, reloadMs);
}

// update accepted — show the spinner pill and poll until the panel reports done
export function updPollStart() {
  if (polling) return;
  clearTimers();
  set({ open: true, key: 'js_upd_running', tone: '', icon: 'check', spinner: true });
  polling = setInterval(async () => {
    try {
      const j = await apiGet('/api/update');
      if (j.running) return;
      clearInterval(polling);
      polling = null;
      if (j.failed) {
        set({ open: true, key: 'js_upd_failed', tone: 'danger', icon: 'x', spinner: false });
        closeLater(2400);
      } else {
        set({ open: true, key: 'js_upd_done', tone: 'good', icon: 'check', spinner: false });
        closeLater(1300, 2300);       // show the check, ripple away, then reload
      }
    } catch { /* panel restarting mid-update — keep polling */ }
  }, 3000);
}

// app boot: pick the droplet back up if an update is already running
// (started before a reload, or from another phone)
export function updResume() {
  apiGet('/api/update').then((j) => { if (j.running) updPollStart(); }).catch(() => {});
}

export function useUpdate() {
  const [, force] = useReducer((x) => x + 1, 0);
  useEffect(() => { subs.add(force); return () => subs.delete(force); }, []);
  return { drop, running: !!polling };
}
