/* Synchrofazotron panel — main page logic (tabs, now-playing view, visualizer
   tab). Header + player bar live in common.js, loaded before this file.
   Served through the i18n filler: {{T:key}} placeholders are replaced
   server-side, so keep translated strings inside single quotes. */

let VIZ = null;               // last /api/viz payload
let lastArtUrl = '';

/* called by common.js after every /api/status poll */
function onStatusUpdate() {
  renderNow();
}

/* ---- "Now playing" tab --------------------------------------------------- */

function artUrl(p) {
  // LMS serves the current track cover itself; other sources have no art
  if (!p || p.id !== 'lms' || !p.playing || !S.lms_playerid) return '';
  return 'http://' + location.hostname + ':{{LMS_PORT}}' +
         '/music/current/cover.jpg?player=' + encodeURIComponent(S.lms_playerid) +
         '&_t=' + encodeURIComponent(p.detail || '');
}

function renderNow() {
  const p = primary();
  const art = $('art');

  const url = artUrl(p);
  if (url !== lastArtUrl) {
    lastArtUrl = url;
    art.style.backgroundImage = url ? 'url("' + url.replace(/"/g, '%22') + '")' : '';
    art.classList.toggle('hasart', !!url);
  }
  art.classList.toggle('playing', !!(p && p.playing));
  art.querySelector('.eq').className = 'eq' + (p && p.playing ? '' : ' off');

  if (!p) {
    $('nowTitle').textContent = '{{T:js_silence}}';
    $('nowSub').textContent = '';
  } else {
    $('nowTitle').textContent = p.detail || p.name;
    $('nowSub').textContent = srcSub(p);
  }

  $('warn').style.display = (S.playing_count >= 2) ? '' : 'none';
}

/* ---- tabs ----------------------------------------------------------------- */

function showTab(name) {
  $('tab-now').style.display = (name === 'now') ? '' : 'none';
  $('tab-viz').style.display = (name === 'viz') ? '' : 'none';
  $('tabBtnNow').classList.toggle('active', name === 'now');
  $('tabBtnViz').classList.toggle('active', name === 'viz');
  try { localStorage.setItem('paneltab', name); } catch (e) {}
  if (name === 'viz') vizRefresh();
}

/* ---- visualizer tab (switching only; editing lives in /settings) ---------- */

async function vizRefresh() {
  try {
    const r = await fetch('/api/viz', {cache:'no-store'});
    VIZ = await r.json();
  } catch (e) { return; }
  const v = VIZ;
  $('vizNA').style.display = v.installed ? 'none' : '';
  $('vizBody').style.display = v.installed ? '' : 'none';
  if (!v.installed) return;

  const glsl = v.engine === 'glsl';
  $('engCava').className = 'btn' + (glsl ? ' sec' : '');
  const g = $('engGlsl');
  g.className = 'btn' + (glsl ? '' : ' sec');
  g.textContent = '{{T:viz_eng_glsl}}' + (v.glsl_available ? '' : ' ⚠');
  g.title = v.glsl_available ? '' : '{{T:viz_glsl_missing}}';
  $('vizErr').textContent = (glsl && v.glsl_error)
    ? '{{T:js_glsl_err}}' + v.glsl_error : '';

  const list = $('vizList');
  list.innerHTML = '';
  const items = glsl ? (v.shaders || []) : (v.presets || []);
  const current = glsl ? v.shader : v.preset;
  items.forEach(it => {
    const b = document.createElement('button');
    b.className = 'btn' + (it.id === current ? '' : ' sec');
    b.textContent = it.label + (it.id === current ? ' ✓' : '');
    b.onclick = () => glsl ? vizEngine('glsl', it.id) : vizPreset(it.id);
    list.appendChild(b);
  });

  $('vizToggle').textContent = v.active ? '{{T:js_viz_stop}}' : '{{T:js_viz_start}}';
}

function vizMsg(t) { $('vizMsg').textContent = t || ''; }

async function vizEngine(engine, shader) {
  try {
    const r = await fetch('/api/viz/engine', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({engine, shader: shader || ''})
    });
    vizMsg((await r.json()).message);
  } catch (e) { vizMsg('{{T:js_conn_error}}'); }
  vizRefresh();
}

async function vizPreset(name) {
  try {
    const r = await fetch('/api/viz/preset', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name})
    });
    vizMsg((await r.json()).message);
  } catch (e) { vizMsg('{{T:js_conn_error}}'); }
  vizRefresh();
}

async function vizToggle() {
  try {
    const r = await fetch('/api/viz/toggle', {method:'POST'});
    vizMsg((await r.json()).message);
  } catch (e) { vizMsg('{{T:js_conn_error}}'); }
  setTimeout(vizRefresh, 500);
}

/* ---- wiring ---------------------------------------------------------------- */

$('tabBtnNow').onclick = () => showTab('now');
$('tabBtnViz').onclick = () => showTab('viz');
$('engCava').onclick = () => vizEngine('cava');
$('engGlsl').onclick = () => vizEngine('glsl');
$('vizToggle').onclick = vizToggle;

let savedTab = 'now';
try { savedTab = localStorage.getItem('paneltab') || 'now'; } catch (e) {}
showTab(savedTab === 'viz' ? 'viz' : 'now');

setInterval(() => {
  if ($('tab-viz').style.display !== 'none') vizRefresh();
}, 10000);
