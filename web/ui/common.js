/* Synchrofazotron panel — logic shared by both pages: the header (pairing
   button) and the bottom player bar with its sources sheet.
   Served through the i18n filler: {{T:key}} placeholders are replaced
   server-side, so keep translated strings inside single quotes. */

const $ = id => document.getElementById(id);

let S = null;                 // last /api/status payload

function escapeHtml(s) {
  return (s || '').replace(/[&<>"']/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

/* the source the player bar (and the main page) follows: first playing one,
   otherwise the first known (paused/connected) one */
function primary() {
  const src = (S && S.sources) || [];
  return src.find(x => x.playing) || src[0] || null;
}

/* subtitle under the track name: artist (LMS only) + source + state */
function srcSub(p) {
  const bits = [];
  if (p.artist) bits.push(p.artist);
  bits.push(p.detail ? (p.name + ' — ' + p.state) : p.state);
  return bits.join(' · ');
}

async function statusRefresh() {
  try {
    const r = await fetch('/api/status', {cache:'no-store'});
    S = await r.json();
  } catch (e) { return; }
  renderPair();
  renderBar();
  renderSheet();
  if (typeof onStatusUpdate === 'function') onStatusUpdate(S);
}

/* ---- header: pairing ------------------------------------------------------ */

function renderPair() {
  const b = $('pairBtn'), label = $('pairLabel');
  if (!b) return;
  const left = S.pair_seconds_left;
  if (left > 0) {
    b.classList.add('active');
    label.textContent = left + 's';
  } else {
    b.classList.remove('active');
    label.textContent = '{{T:pair_short}}';
  }
}

async function pair() {
  const b = $('pairBtn');
  b.disabled = true;
  try { await fetch('/api/pair', {method:'POST'}); } catch (e) {}
  b.disabled = false;
  statusRefresh();
}

/* ---- player bar ------------------------------------------------------------ */

function renderBar() {
  if (!$('pbPlay')) return;
  const p = primary();
  $('pbEq').className = 'eq' + (p && p.playing ? '' : ' off');
  if (!p) {
    $('pbTitle').textContent = '{{T:js_silence}}';
    $('pbSub').textContent = '';
  } else {
    $('pbTitle').textContent = p.detail || p.name;
    $('pbSub').textContent = srcSub(p);
  }
  const btn = $('pbPlay');
  btn.disabled = !(p && p.controllable && p.id);
  btn.title = btn.disabled ? '{{T:js_ctrl_hint}}' : '';
  $('pbIconPlay').style.display = (p && p.playing) ? 'none' : '';
  $('pbIconPause').style.display = (p && p.playing) ? '' : 'none';
}

async function ctrl(id) {
  try {
    await fetch('/api/control', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({source: id, action: 'toggle'})
    });
  } catch (e) {}
  setTimeout(statusRefresh, 500);
}

/* ---- source sheet (arrow on the bar) ------------------------------------------ */

function renderSheet() {
  const box = $('sheetList');
  if (!box) return;
  const src = (S && S.sources) || [];
  if (!src.length) {
    box.innerHTML = '<p class="muted">{{T:js_silence}}</p>';
  } else {
    box.innerHTML = '';
    src.forEach(x => {
      const row = document.createElement('div');
      row.className = 'srow';
      const info = document.createElement('div');
      info.className = 'info';
      info.innerHTML =
        '<span class="eq' + (x.playing ? '' : ' off') + '"><i></i><i></i><i></i></span> ' +
        '<b>' + escapeHtml(x.name) + '</b> — ' + escapeHtml(x.state) +
        (x.detail ? '<div class="det">' + escapeHtml(x.detail) + '</div>' : '');
      const btn = document.createElement('button');
      btn.className = 'tbtn' + (x.playing ? ' playing' : '');
      btn.textContent = x.playing ? '⏸' : '▶';
      if (x.controllable && x.id) {
        btn.onclick = () => ctrl(x.id);
      } else {
        btn.disabled = true;
        btn.title = '{{T:js_ctrl_hint}}';
      }
      row.appendChild(info);
      row.appendChild(btn);
      box.appendChild(row);
    });
  }

  // who holds the audio output (an open-but-silent stream still blocks the DAC)
  const own = S.dac_owners || [];
  $('dacline').innerHTML = own.length
    ? '{{T:js_dac_owner}}' + own.map(o =>
        '<b>' + escapeHtml(o.label) + '</b>' +
        (o.running ? '' : ' {{T:js_dac_hold}}')).join(', ')
    : '{{T:js_dac_free}}';
}

/* ---- wiring ---------------------------------------------------------------------- */

if ($('pairBtn')) $('pairBtn').onclick = pair;
if ($('srcArrow')) $('srcArrow').onclick = () => $('pbwrap').classList.toggle('open');
if ($('pbPlay')) $('pbPlay').onclick = () => {
  const p = primary();
  if (p && p.controllable && p.id) ctrl(p.id);
};

statusRefresh();
setInterval(statusRefresh, 3000);
