// PC plugin — Settings card. Plain ES module: no build step, everything comes
// from the panel's runtime SDK (window.sfz, see web/app/src/plugins.js).
// Props from the panel: plugin (manifest), t (plugin strings in the panel's
// language), api ({get, post, path} scoped to /api/p/pc).
const { html, hooks: { useEffect, useState }, useApi, useToast, Collapsible } = window.sfz;

export function SettingsCard({ t, api }) {
  const toast = useToast();
  const [st, reload] = useApi(api.path('/state'), 5000);
  const [busy, setBusy] = useState(false);
  const [edit, setEdit] = useState(false);
  const [mac, setMac] = useState('');
  const [host, setHost] = useState('');
  const [msg, setMsg] = useState('');

  // First state load fills the form; later polls must not clobber typing.
  useEffect(() => {
    if (st && !edit) { setMac(st.mac || ''); setHost(st.host || ''); }
  }, [st]);

  const wake = async () => {
    setBusy(true);
    try {
      const j = await api.post('/wake');
      toast(t(j.message || (j.ok ? 'sent' : 'no_mac')));
    } catch { toast('✕'); }
    setBusy(false);
    reload();
  };

  const save = async () => {
    setBusy(true);
    try {
      const j = await api.post('/config', { mac, host });
      setMsg(t(j.message || 'saved'));
      if (j.ok) { setEdit(false); reload(); }
    } catch { setMsg('✕'); }
    setBusy(false);
  };

  const hasMac = !!(st && st.mac);
  const online = st ? st.online : null;
  const pill = online == null ? null
    : html`<span class=${'pill ' + (online ? 'on' : 'off')}>${t(online ? 'online' : 'offline')}</span>`;
  const last = st && st.last_wake
    ? new Date(st.last_wake * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '';

  return html`
    <div class="card">
      <div class="card-head">
        <h2><i class="ico ico-power"></i> ${t('head')}</h2>
        ${pill}
      </div>
      <p class="muted">${t('note')}</p>
      <button class="btn" disabled=${busy || !hasMac} onClick=${wake}>
        ${busy ? t('waking') : t('wake')}
      </button>
      ${!hasMac && st && html`<p class="muted small">${t('no_mac')}</p>`}
      ${last && html`<p class="muted small">${t('last_wake')}: ${last}</p>`}
      <button class="btn sec" onClick=${() => { setEdit(!edit); setMsg(''); }}>
        ${st && st.mac ? html`<code>${st.mac}</code>` : t('mac')} ${edit ? '▴' : '▾'}
      </button>
      <${Collapsible} open=${edit}>
        <label class="fieldlabel muted">${t('mac')}</label>
        <input value=${mac} placeholder="AA:BB:CC:DD:EE:FF" autocomplete="off" spellcheck="false"
               onInput=${(e) => setMac(e.currentTarget.value)} />
        <p class="muted small">${t('mac_hint')}</p>
        <label class="fieldlabel muted">${t('host')}</label>
        <input value=${host} placeholder="192.168.1.20" autocomplete="off" spellcheck="false"
               onInput=${(e) => setHost(e.currentTarget.value)} />
        <p class="muted small">${t('host_hint')}</p>
        <button class="btn" disabled=${busy} onClick=${save}>${t('save')}</button>
        ${msg && html`<p class="muted">${msg}</p>`}
      <//>
    </div>`;
}
