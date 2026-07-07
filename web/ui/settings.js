/* Synchrofazotron panel — settings page logic. Loaded after common.js
   (escapeHtml, header pairing + player bar live there).
   Served through the i18n filler: {{T:key}} placeholders are replaced
   server-side, so keep translated strings inside single quotes. */

function msg(t) { document.getElementById('msg').textContent = t; }
function modalMsg(t) { document.getElementById('modalMsg').textContent = t; }

/* ---- config: network status + saved networks ----------------------------- */

async function refresh() {
  try {
    const r = await fetch('/api/wifi', {cache:'no-store'});
    const w = await r.json();
    const cur = w.current;
    document.getElementById('wifiNow').innerHTML = cur
      ? '<span class="pill on">{{T:js_wifi_connected}}</span> <b>' + escapeHtml(cur.ssid) + '</b>'
        + (cur.ip ? ' — ' + cur.ip : '')
        + (cur.signal != null ? ' <span class="muted">(' + cur.signal + ' dBm)</span>' : '')
      : '<span class="pill off">{{T:js_wifi_none}}</span>';
    // addresses "just in case" — how to reach the panel if MagicDNS fails
    const bits = [];
    if (cur && cur.ip) bits.push('{{T:js_lan_ip}}<code>' + cur.ip + '</code>');
    if (w.tailscale_ip) bits.push('{{T:js_ts_ip}}<code>' + w.tailscale_ip + '</code>');
    if (w.hostname) bits.push('<code>' + escapeHtml(w.hostname) + '</code>');
    document.getElementById('netInfo').innerHTML = bits.join(' · ');
    const box = document.getElementById('saved');
    const saved = w.saved || [];
    box.innerHTML = saved.length ? saved.map(s =>
      '<div class="row"><div class="info">' +
      (cur && cur.ssid === s.ssid ? '<i class="dot on"></i> ' : '') +
      '<b>' + escapeHtml(s.ssid) + '</b>' +
      ' <span class="muted">{{T:js_slot}}' + s.slot + '</span></div>' +
      '<button class="xbtn" title="{{T:js_remove}}" onclick="removeNet(' + s.slot + ',\'' +
      escapeHtml(s.ssid).replace(/'/g, "\\'") + '\')"><i class="ico ico-trash"></i></button></div>'
    ).join('') : '<p class="muted">{{T:js_no_saved}}</p>';
  } catch(e) {}
}

/* ---- config: "Add a network" modal ---------------------------------------- */

function wifiModal(open) {
  document.getElementById('wifiOverlay').classList.toggle('open', !!open);
  if (open) {
    modalMsg('');
    document.getElementById('scanOut').innerHTML = '';
    document.getElementById('ssid').focus();
  }
}

document.getElementById('wifiOverlay').onclick = e => {
  if (e.target === e.currentTarget) wifiModal(false);
};

async function addNet() {
  const ssid = document.getElementById('ssid').value;
  const key = document.getElementById('key').value;
  const b = document.getElementById('addBtn');
  b.disabled = true; modalMsg('{{T:js_saving}}');
  try {
    const r = await fetch('/api/wifi/add', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ssid, key})
    });
    const j = await r.json();
    if (j.ok) {
      document.getElementById('ssid').value = '';
      document.getElementById('key').value = '';
      wifiModal(false);
      msg(j.message || 'OK');
    } else {
      modalMsg(j.message || '{{T:js_error}}');
    }
  } catch(e) { modalMsg('{{T:js_conn_error}}'); }
  b.disabled = false;
  refresh();
}

async function removeNet(slot, ssid) {
  if (!confirm('{{T:js_rm_pre}}' + ssid + '{{T:js_rm_suf}}')) return;
  try {
    const r = await fetch('/api/wifi/remove', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({slot})
    });
    const j = await r.json();
    msg(j.message || '');
  } catch(e) { msg('{{T:js_conn_error}}'); }
  refresh();
}

async function scan() {
  const b = document.getElementById('scanBtn');
  b.disabled = true; b.textContent = '{{T:js_scanning}}';
  try {
    const r = await fetch('/api/wifi/scan', {cache:'no-store'});
    const j = await r.json();
    const nets = j.networks || [];
    document.getElementById('scanOut').innerHTML = nets.length
      ? nets.map(n =>
          '<button class="btn sec netbtn" onclick="pick(\'' +
          escapeHtml(n.ssid).replace(/'/g, "\\'") + '\')">' +
          escapeHtml(n.ssid) + ' <span class="muted">' + n.signal + ' dBm</span></button>'
        ).join('')
      : '<p class="muted">{{T:js_scan_none}}</p>';
  } catch(e) { modalMsg('{{T:js_scan_fail}}'); }
  b.disabled = false; b.textContent = '{{T:wifi_scan_btn}}';
}

function pick(ssid) {
  document.getElementById('ssid').value = ssid;
  document.getElementById('key').focus();
}

/* ---- config: tailscale ------------------------------------------------------ */

async function tsRefresh() {
  try {
    const r = await fetch('/api/tailscale', {cache:'no-store'});
    const t = await r.json();
    const sw = document.getElementById('tsSwitch');
    sw.checked = t.active;
    sw.disabled = !t.installed;
    document.getElementById('tsState').innerHTML = !t.installed
      ? '{{T:ts_missing}}'
      : (t.active
          ? '<span class="pill on">{{T:js_wifi_connected}}</span>'
            + (t.ip ? ' <code>' + t.ip + '</code>' : '')
          : '<span class="pill off">{{T:js_off}}</span>');
  } catch(e) {}
}

document.getElementById('tsSwitch').onchange = async () => {
  const sw = document.getElementById('tsSwitch');
  const up = sw.checked;
  if (!up && !confirm('{{T:js_src_off_pre}}Tailscale{{T:js_src_off_suf}}')) {
    sw.checked = true;
    return;
  }
  sw.disabled = true;
  try {
    const r = await fetch('/api/tailscale/set', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({up})
    });
    const j = await r.json();
    document.getElementById('tsMsg').textContent = j.message || '';
  } catch(e) { document.getElementById('tsMsg').textContent = '{{T:js_conn_error}}'; }
  tsRefresh();
};

/* ---- config: language -------------------------------------------------------- */

const langSel = document.getElementById('langSel');
langSel.value = document.documentElement.lang || 'en';
langSel.onchange = () => setLang(langSel.value);

async function setLang(lang) {
  try {
    await fetch('/api/lang', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({lang})
    });
  } catch(e) {}
  location.reload();
}

/* ---- sources: enable/disable + service dots ----------------------------------- */

let SRC = null;

async function srcRefresh() {
  try {
    const r = await fetch('/api/sources', {cache:'no-store'});
    SRC = await r.json();
  } catch(e) { return; }
  (SRC.sources || []).forEach(g => {
    const sw = document.getElementById('sw_' + g.id);
    if (!sw) return;                       // e.g. spotify card stripped
    sw.checked = g.enabled;
    sw.disabled = !g.installed;
    const hint = document.getElementById('hint_' + g.id);
    if (hint) hint.style.display = (g.installed && !g.enabled) ? '' : 'none';
    const dots = document.getElementById('dots_' + g.id);
    if (dots) {
      dots.innerHTML = g.installed
        ? g.services.map(s =>
            '<span><i class="dot ' +
            (s.active ? 'on' : (g.enabled ? 'err' : '')) + '"></i>' +
            escapeHtml(s.name) + '</span>').join('')
        : '<span class="pill off">{{T:src_not_installed}}</span>';
    }
  });
}

function srcLabel(id) {
  const g = SRC && (SRC.sources || []).find(x => x.id === id);
  return g ? g.label : id;
}

['bluetooth', 'airplay', 'lms', 'spotify'].forEach(id => {
  const sw = document.getElementById('sw_' + id);
  if (!sw) return;
  sw.onchange = async () => {
    const enable = sw.checked;
    if (!enable &&
        !confirm('{{T:js_src_off_pre}}' + srcLabel(id) + '{{T:js_src_off_suf}}')) {
      sw.checked = true;
      return;
    }
    sw.disabled = true;
    try {
      const r = await fetch('/api/source/toggle', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({source: id, enable})
      });
      const j = await r.json();
      document.getElementById('msg_' + id).textContent = j.message || '';
    } catch(e) {
      document.getElementById('msg_' + id).textContent = '{{T:js_conn_error}}';
    }
    srcRefresh();
    btRefresh();
  };
});

/* ---- sources: bluetooth device management --------------------------------------- */

let btBusy = false;

async function btRefresh() {
  if (btBusy) return;  // do not repaint the list mid-connect
  try {
    const r = await fetch('/api/bt', {cache:'no-store'});
    const b = await r.json();
    const list = b.paired || [];
    document.getElementById('btDevices').innerHTML = list.length ? list.map(d =>
      '<div class="row"><div class="info" style="cursor:pointer;" ' +
      'onclick="btConnect(\'' + d.mac + '\')">' +
      '<i class="dot' + (d.connected ? ' on' : '') + '"></i> ' +
      '<b>' + escapeHtml(d.name) + '</b></div>' +
      (d.connected
        ? '<button class="xbtn" title="{{T:js_bt_disconnect}}" ' +
          'onclick="btDisconnect(\'' + d.mac + '\')">✕</button>'
        : '') +
      '<button class="xbtn" title="{{T:bt_forget_title}}" ' +
      'onclick="btForget(\'' + d.mac + '\',\'' +
      escapeHtml(d.name).replace(/'/g, "\\'") + '\')"><i class="ico ico-trash"></i></button>' +
      '</div>'
    ).join('') : '<p class="muted">{{T:js_bt_none}}</p>';
  } catch(e) {}
}

async function btConnect(mac) {
  if (btBusy) return;
  btBusy = true;
  document.getElementById('btMsg').textContent = '{{T:js_bt_connecting}}';
  try {
    const r = await fetch('/api/bt/connect', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({mac})
    });
    const j = await r.json();
    document.getElementById('btMsg').textContent = j.message || '';
  } catch(e) { document.getElementById('btMsg').textContent = '{{T:js_conn_error}}'; }
  btBusy = false;
  btRefresh();
}

async function btDisconnect(mac) {
  btBusy = true;
  try {
    const r = await fetch('/api/bt/disconnect', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({mac})
    });
    const j = await r.json();
    document.getElementById('btMsg').textContent = j.message || '';
  } catch(e) {}
  btBusy = false;
  btRefresh();
}

async function btForget(mac, name) {
  if (!confirm('{{T:js_bt_forget_pre}}' + name + '{{T:js_bt_forget_suf}}')) return;
  btBusy = true;
  try {
    const r = await fetch('/api/bt/forget', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({mac})
    });
    const j = await r.json();
    document.getElementById('btMsg').textContent = j.message || '';
  } catch(e) { document.getElementById('btMsg').textContent = '{{T:js_conn_error}}'; }
  btBusy = false;
  btRefresh();
}

async function btTest() {
  const b = document.getElementById('btTestBtn');
  b.disabled = true;
  document.getElementById('btMsg').textContent = '{{T:js_bt_testing}}';
  try {
    const r = await fetch('/api/audio/test', {method:'POST'});
    const j = await r.json();
    document.getElementById('btMsg').textContent = j.message || '';
  } catch(e) { document.getElementById('btMsg').textContent = '{{T:js_conn_error}}'; }
  b.disabled = false;
}

async function btDebug() {
  const el = document.getElementById('btReport');
  el.style.display = '';
  el.textContent = '…';
  try {
    const r = await fetch('/api/bt/debug', {cache:'no-store'});
    const j = await r.json();
    el.textContent = j.report || '';
  } catch(e) { el.textContent = '{{T:js_conn_error}}'; }
}

/* ---- visualizer ------------------------------------------------------------------ */

let VIZ = null, vizEditing = null;

async function vizRefresh() {
  try {
    const r = await fetch('/api/viz', {cache:'no-store'});
    const v = await r.json();
    VIZ = v;
    // not installed: keep the card visible, explain instead of hiding
    document.getElementById('vizNA').style.display = v.installed ? 'none' : '';
    document.getElementById('vizBody').style.display = v.installed ? '' : 'none';
    if (!v.installed) return;
    document.getElementById('vizPresets').innerHTML = (v.presets||[]).map(p =>
      '<div class="prow"><button class="btn ' + (p.id === v.preset ? '' : 'sec') + '" ' +
      'onclick="vizPreset(\'' + p.id + '\')">' + escapeHtml(p.label) +
      (p.id === v.preset ? ' ✓' : '') + '</button>' +
      '<button class="ebtn" title="{{T:viz_edit_title}}" ' +
      'onclick="vizEdit(\'' + p.id + '\')">✎</button></div>'
    ).join('');
    document.getElementById('vizToggle').textContent =
      v.active ? '{{T:js_viz_stop}}' : '{{T:js_viz_start}}';
    // engine switch — the glsl button stays visible even when the engine is
    // unusable: it gets a warning marker and the click explains what is missing
    const glsl = v.engine === 'glsl';
    document.getElementById('engCava').className = 'btn' + (glsl ? ' sec' : '');
    const g = document.getElementById('engGlsl');
    g.className = 'btn' + (glsl ? '' : ' sec');
    g.textContent = '{{T:viz_eng_glsl}}' + (v.glsl_available ? '' : ' ⚠');
    g.title = v.glsl_available ? '' : '{{T:viz_glsl_missing}}';
    document.getElementById('vizCavaCtl').style.display = glsl ? 'none' : '';
    document.getElementById('vizErr').textContent =
      (glsl && v.glsl_error) ? '{{T:js_glsl_err}}' + v.glsl_error : '';
    document.getElementById('vizShaders').innerHTML = (glsl ? (v.shaders||[]) : []).map(s =>
      '<div class="prow"><button class="btn ' + (s.id === v.shader ? '' : 'sec') + '" ' +
      'onclick="vizShader(\'' + s.id + '\')">' + escapeHtml(s.label) +
      (s.id === v.shader ? ' ✓' : '') + '</button>' +
      (s.id === v.shader ? '' :
        '<button class="ebtn" title="{{T:sdel_title}}" ' +
        'onclick="shaderDel(\'' + s.id + '\')"><i class="ico ico-trash"></i></button>') +
      '</div>'
    ).join('');
    document.getElementById('shaderDrop').style.display = glsl ? '' : 'none';
  } catch(e) {}
}

async function vizEngine(engine, shader) {
  try {
    const r = await fetch('/api/viz/engine', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({engine, shader: shader || ''})
    });
    const j = await r.json();
    document.getElementById('vizMsg').textContent = j.message || '';
  } catch(e) {}
  vizRefresh();
}

function vizShader(name) { vizEngine('glsl', name); }

// --- shader upload (drag & drop / file picker) ---
async function shaderFiles(files) {
  for (const f of files) {
    let src = '';
    try { src = await f.text(); } catch(e) { continue; }
    try {
      const r = await fetch('/api/viz/shader/upload', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({name: f.name, source: src})
      });
      const j = await r.json();
      document.getElementById('vizMsg').textContent = j.message || '';
    } catch(e) { document.getElementById('vizMsg').textContent = '{{T:js_conn_error}}'; }
  }
  document.getElementById('shaderFile').value = '';
  vizRefresh();
}

async function shaderDel(id) {
  const s = VIZ && (VIZ.shaders||[]).find(x => x.id === id);
  if (!s || !confirm('{{T:js_sdel_pre}}' + s.label + '{{T:js_sdel_suf}}')) return;
  try {
    const r = await fetch('/api/viz/shader/delete', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id})
    });
    const j = await r.json();
    document.getElementById('vizMsg').textContent = j.message || '';
  } catch(e) { document.getElementById('vizMsg').textContent = '{{T:js_conn_error}}'; }
  vizRefresh();
}

(function wireShaderDrop() {
  const drop = document.getElementById('shaderDrop');
  drop.onclick = () => document.getElementById('shaderFile').click();
  drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); };
  drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = e => {
    e.preventDefault(); drop.classList.remove('over');
    shaderFiles(e.dataTransfer.files);
  };
  document.getElementById('shaderFile').onchange = e => shaderFiles(e.target.files);
})();

function vizFillEditor(p) {
  for (const [id, val] of [['v_fr', p.framerate], ['v_bw', p.bar_width],
                           ['v_bs', p.bar_spacing], ['v_nr', p.noise_reduction]]) {
    document.getElementById(id).value = val;
    document.getElementById(id + '_v').textContent = val;
  }
  document.getElementById('v_mc').checked = !!p.monstercat;
  document.getElementById('v_wv').checked = !!p.waves;
  const sel = document.getElementById('v_color');
  sel.innerHTML = (p.colors||[]).map(c =>
    '<option' + (c === p.color ? ' selected' : '') + '>' + c + '</option>').join('');
}

// opens the editor for a preset (id) or for a brand-new one (null)
function vizEdit(id) {
  if (!VIZ) return;
  vizEditing = id || '';
  const p = id ? (VIZ.presets||[]).find(x => x.id === id) : null;
  document.getElementById('v_name').value = p ? p.label : '';
  const params = Object.assign({}, p ? p.params : (VIZ.params || {}));
  params.colors = (VIZ.params || {}).colors || [];
  vizFillEditor(params);
  document.getElementById('vizDelBtn').style.display = p ? '' : 'none';
  document.getElementById('vizEdit').style.display = '';
  document.getElementById('v_name').focus();
}

function vizEditorBody() {
  const num = id => +document.getElementById(id).value;
  return { framerate: num('v_fr'), bar_width: num('v_bw'), bar_spacing: num('v_bs'),
           noise_reduction: num('v_nr'),
           monstercat: document.getElementById('v_mc').checked,
           waves: document.getElementById('v_wv').checked,
           color: document.getElementById('v_color').value };
}

async function vizApply() {
  try {
    const r = await fetch('/api/viz/params', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(vizEditorBody())
    });
    const j = await r.json();
    document.getElementById('vizMsg').textContent = j.message || '';
  } catch(e) { document.getElementById('vizMsg').textContent = '{{T:js_conn_error}}'; }
  vizRefresh();
}

async function vizSavePreset() {
  const body = vizEditorBody();
  body.id = vizEditing || '';
  body.label = document.getElementById('v_name').value;
  try {
    const r = await fetch('/api/viz/preset/save', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    const j = await r.json();
    document.getElementById('vizMsg').textContent = j.message || '';
    if (j.ok) document.getElementById('vizEdit').style.display = 'none';
  } catch(e) { document.getElementById('vizMsg').textContent = '{{T:js_conn_error}}'; }
  vizRefresh();
}

async function vizDelPreset() {
  const p = VIZ && (VIZ.presets||[]).find(x => x.id === vizEditing);
  if (!p || !confirm('{{T:js_vdel_pre}}' + p.label + '{{T:js_vdel_suf}}')) return;
  try {
    const r = await fetch('/api/viz/preset/delete', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: vizEditing})
    });
    const j = await r.json();
    document.getElementById('vizMsg').textContent = j.message || '';
    if (j.ok) document.getElementById('vizEdit').style.display = 'none';
  } catch(e) { document.getElementById('vizMsg').textContent = '{{T:js_conn_error}}'; }
  vizRefresh();
}

async function vizPreset(name) {
  try {
    const r = await fetch('/api/viz/preset', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name})
    });
    const j = await r.json();
    document.getElementById('vizMsg').textContent = j.message || '';
  } catch(e) {}
  vizRefresh();
}

async function vizToggle() {
  try {
    const r = await fetch('/api/viz/toggle', {method:'POST'});
    const j = await r.json();
    document.getElementById('vizMsg').textContent = j.message || '';
  } catch(e) {}
  setTimeout(vizRefresh, 500);
}

/* ---- config: audio output ------------------------------------------------------- */

async function audioRefresh() {
  try {
    const r = await fetch('/api/audio', {cache:'no-store'});
    const a = await r.json();
    const d = document.getElementById('audioDac');
    const h = document.getElementById('audioHdmi');
    d.className = 'btn' + (a.output === 'dac' ? '' : ' sec');
    h.className = 'btn' + (a.output === 'hdmi' ? '' : ' sec');
    d.textContent = 'DAC' + (a.output === 'dac' ? ' ✓' : '');
    h.textContent = 'HDMI' + (a.output === 'hdmi' ? ' ✓' : '');
    document.getElementById('rebootBtn').style.display =
      a.reboot_required ? '' : 'none';
    if (a.reboot_required)
      document.getElementById('audioMsg').textContent = '{{T:js_audio_reboot}}';
  } catch(e) {}
}

async function audioSet(mode) {
  if (!confirm('{{T:js_audio_confirm}}')) return;
  try {
    const r = await fetch('/api/audio/set', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({output: mode})
    });
    const j = await r.json();
    document.getElementById('audioMsg').textContent = j.message || '';
  } catch(e) {
    document.getElementById('audioMsg').textContent = '{{T:js_conn_error}}';
  }
  audioRefresh();
}

async function doReboot() {
  if (!confirm('{{T:js_reboot_confirm}}')) return;
  try { await fetch('/api/reboot', {method:'POST'}); } catch(e) {}
  document.getElementById('audioMsg').textContent = '{{T:js_rebooting}}';
}

/* ---- config: updates --------------------------------------------------------------- */

function updMsg(t) { document.getElementById('updMsg').textContent = t; }

async function updCheck() {
  const b = document.getElementById('updCheckBtn');
  b.disabled = true; updMsg('{{T:js_upd_checking}}');
  try {
    const r = await fetch('/api/update/check', {cache:'no-store'});
    const j = await r.json();
    updMsg(!j.ok ? '{{T:js_upd_checkfail}}'
           : (j.update_available ? '{{T:js_upd_available}}' : '{{T:js_upd_current}}'));
  } catch(e) { updMsg('{{T:js_conn_error}}'); }
  b.disabled = false;
}

let updTimer = null;
function updPoll() {
  if (updTimer) return;
  document.getElementById('updRunBtn').disabled = true;
  updMsg('{{T:js_upd_running}}');
  updTimer = setInterval(async () => {
    try {
      const r = await fetch('/api/update', {cache:'no-store'});
      const j = await r.json();
      if (j.running) return;
      clearInterval(updTimer); updTimer = null;
      document.getElementById('updRunBtn').disabled = false;
      if (j.failed) { updMsg('{{T:js_upd_failed}}'); }
      else { updMsg('{{T:js_upd_done}}'); setTimeout(() => location.reload(), 1500); }
    } catch(e) { /* panel restarting mid-update — keep polling */ }
  }, 3000);
}

async function updRun() {
  if (!confirm('{{T:js_upd_confirm}}')) return;
  try {
    const r = await fetch('/api/update/run', {method:'POST'});
    const j = await r.json();
    if (!j.ok) { updMsg(j.message || '{{T:js_error}}'); return; }
    updPoll();
  } catch(e) { updMsg('{{T:js_conn_error}}'); }
}

// page opened (or reloaded) while an update is already running -> resume the poll
fetch('/api/update', {cache:'no-store'}).then(r => r.json())
  .then(j => { if (j.running) updPoll(); }).catch(() => {});

/* ---- section nav: one section visible at a time -------------------------------------- */

function showSection(id) {
  if (!document.getElementById(id)) id = 'config';
  document.querySelectorAll('.content section').forEach(s =>
    s.classList.toggle('active', s.id === id));
  document.querySelectorAll('#snav a').forEach(a =>
    a.classList.toggle('active', a.getAttribute('href') === '#' + id));
  try { localStorage.setItem('settingstab', id); } catch(e) {}
}

document.querySelectorAll('#snav a').forEach(a => {
  a.onclick = e => {
    e.preventDefault();
    const id = a.getAttribute('href').slice(1);
    history.replaceState(null, '', '#' + id);
    showSection(id);
  };
});

let startSection = (location.hash || '').slice(1);
if (!startSection) {
  try { startSection = localStorage.getItem('settingstab') || ''; } catch(e) {}
}
showSection(startSection || 'config');

/* ---- editor slider labels ------------------------------------------------------------ */

['v_fr','v_bw','v_bs','v_nr'].forEach(id => {
  document.getElementById(id).oninput = e =>
    document.getElementById(id + '_v').textContent = e.target.value;
});

/* ---- init ------------------------------------------------------------------------------ */

refresh();
btRefresh();
srcRefresh();
tsRefresh();
vizRefresh();
audioRefresh();
setInterval(refresh, 8000);
setInterval(btRefresh, 5000);
setInterval(srcRefresh, 10000);
setInterval(tsRefresh, 15000);
