// Local UI preferences (per phone/browser, not device state) — plain
// localStorage flags read synchronously at render time.

// Smooth radio loading: slide-in on list changes + skeleton rows while a
// station list loads. On by default; the Experimental card can switch it off.
export function radioFx() {
  try { return localStorage.getItem('radioFx') !== '0'; } catch { return true; }
}

export function setRadioFx(on) {
  try { localStorage.setItem('radioFx', on ? '1' : '0'); } catch { /* no storage */ }
}
