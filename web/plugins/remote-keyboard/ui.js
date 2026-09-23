// Remote Keyboard plugin — Settings card. Plain ES module on the panel's
// runtime SDK (window.sfz, see web/app/src/plugins.js). Props from the panel:
// plugin (manifest), t (plugin strings in the panel's language), api
// ({get, post, path} scoped to /api/p/remote-keyboard).
const { html, hooks: { useEffect, useState }, useApi, useToast, apiUrl, Collapsible } = window.sfz;

const fmt = (s, n) => s.replace('%s', n);

// The keyboard icon is not in the panel's set — ship it in style.css and
// inject the stylesheet once (version-stamped like ui.js).
function useStyle(plugin) {
  useEffect(() => {
    const id = 'sfz-remote-keyboard-css';
    if (document.getElementById(id)) return;
    const link = document.createElement('link');
    link.id = id; link.rel = 'stylesheet';
    link.href = apiUrl(`/plugins/remote-keyboard/style.css?v=${encodeURIComponent(plugin.version || '')}`);
    document.head.appendChild(link);
  }, []);
}

export function SettingsCard({ plugin, t, api }) {
  useStyle(plugin);
  const toast = useToast();
  const [st, reload] = useApi(api.path('/state'), 5000);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [more, setMore] = useState(false);
  const [edit, setEdit] = useState(false);
  const [layout, setLayout] = useState('pl');
  const [msg, setMsg] = useState('');

  // First state load fills the settings form; later polls must not clobber it.
  useEffect(() => { if (st && !edit) setLayout(st.layout || 'pl'); }, [st]);

  const status = st ? st.status : null;
  const blocked = status === 'reboot' || status === 'no_gadget';

  const send = async () => {
    if (!text) return;
    setBusy(true);
    try {
      const j = await api.post('/type', { text });
      if (j.ok) {
        setText('');
        toast(j.skipped ? fmt(t('skipped'), j.skipped) : t('typed'));
      } else toast(t(j.message || 'write_fail'));
    } catch { toast('✕'); }
    setBusy(false);
    reload();
  };

  const key = async (name) => {
    setBusy(true);
    try {
      const j = await api.post('/key', { key: name });
      if (!j.ok) toast(t(j.message || 'write_fail'));
    } catch { toast('✕'); }
    setBusy(false);
  };

  const save = async () => {
    setBusy(true);
    try {
      const j = await api.post('/config', { layout });
      setMsg(t(j.message || 'saved'));
      if (j.ok) { setEdit(false); reload(); }
    } catch { setMsg('✕'); }
    setBusy(false);
  };

  const pill = status && status !== 'sandbox'
    ? html`<span class=${'pill ' + (status === 'ready' ? 'on' : 'off')}>${t(status)}</span>`
    : null;
  const hint = status && status !== 'ready' && status !== 'sandbox'
    ? html`<p class="muted small">${t('hint_' + status)}</p>` : null;
  const keyBtn = (name, label) => html`
    <button class="btn sec" disabled=${busy || blocked} onClick=${() => key(name)}
            aria-label=${label} title=${label}>${label}</button>`;

  return html`
    <div class="card">
      <div class="card-head">
        <h2><i class="ico ico-keyboard"></i> ${t('head')}</h2>
        ${pill}
      </div>
      <p class="muted">${t('note')}</p>
      ${hint}
      <input value=${text} placeholder=${t('placeholder')} autocomplete="off" autocapitalize="off"
             spellcheck="false" enterkeyhint="send" disabled=${blocked}
             onInput=${(e) => setText(e.currentTarget.value)}
             onKeyDown=${(e) => { if (e.key === 'Enter') { e.preventDefault(); send(); } }} />
      <button class="btn" disabled=${busy || blocked || !text} onClick=${send}>
        ${busy ? t('sending') : t('send')}
      </button>
      <div class="prow">
        ${keyBtn('backspace', '⌫ ' + t('backspace'))}
        ${keyBtn('enter', '⏎ ' + t('enter'))}
      </div>
      <button class="btn sec" disabled=${blocked} onClick=${() => setMore(true)}>${t('more')}</button>

      <button class="btn sec" onClick=${() => { setEdit(!edit); setMsg(''); }}>
        ${t('settings')} ${edit ? '▴' : '▾'}
      </button>
      <${Collapsible} open=${edit}>
        <label class="fieldlabel muted">${t('layout')}</label>
        <select value=${layout} onChange=${(e) => setLayout(e.currentTarget.value)}>
          <option value="pl">${t('layout_pl')}</option>
          <option value="us">${t('layout_us')}</option>
        </select>
        <p class="muted small">${t('layout_hint')}</p>
        <button class="btn" disabled=${busy} onClick=${save}>${t('save')}</button>
        ${msg && html`<p class="muted">${msg}</p>`}
      <//>

      ${more && html`
        <div class="overlay open" onClick=${(e) => e.target === e.currentTarget && setMore(false)}>
          <div class="modal">
            <h2><i class="ico ico-keyboard"></i> ${t('more_head')}</h2>
            <p class="muted">${t('more_note')}</p>
            <div class="prow">
              ${keyBtn('esc', t('esc'))}
              ${keyBtn('up', '↑')}
              ${keyBtn('delete', t('delete'))}
            </div>
            <div class="prow">
              ${keyBtn('left', '←')}
              ${keyBtn('down', '↓')}
              ${keyBtn('right', '→')}
            </div>
            <button class="btn sec" onClick=${() => setMore(false)}>${t('close')}</button>
          </div>
        </div>`}
    </div>`;
}
