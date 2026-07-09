import { useRef, useState } from 'preact/hooks';
import { useI18n } from '../../i18n.jsx';
import { apiPost } from '../../api.js';
import { apiUrl } from '../../host.js';
import { useApi } from '../../hooks.js';
import { Collapsible } from '../../components/Collapsible.jsx';
import { Tabs } from '../../components/Tabs.jsx';
import { EmptyState } from '../../components/EmptyState.jsx';

export function VisualizerSection() {
  const { t } = useI18n();
  const [v, reload] = useApi('/api/viz', 0);
  const [msg, setMsg] = useState('');
  const [pending, setPending] = useState(null);   // optimistic switch state

  const engine = async (eng, shader) => {
    try { setMsg((await apiPost('/api/viz/engine', { engine: eng, shader: shader || '' })).message || ''); }
    catch { /* ignore */ }
    reload();
  };
  const toggle = async () => {
    setPending(!on);
    try { setMsg((await apiPost('/api/viz/toggle')).message || ''); } catch { /* ignore */ }
    await new Promise((r) => setTimeout(r, 600));   // the service takes a beat
    await reload();
    setPending(null);
  };

  const installed = !!(v && v.installed);
  const on = pending != null ? pending : !!(v && v.enabled);
  const glsl = v && v.engine === 'glsl';

  return (
    <section class="active">
      <div class="sect-title">{t('nav_viz')}</div>
      <div class="cardgrid">
        <div class="card">
          <div class="card-head">
            <h2><i class="ico ico-chart"></i> {t('viz_head')}</h2>
            {installed && (
              <label class="switch">
                <input type="checkbox" checked={on} onChange={toggle} />
                <span class="knob"></span>
              </label>
            )}
          </div>
          <p class="muted">{t('viz_note')}</p>
          {!v
            ? <p class="muted">…</p>
            : !v.installed
              ? <p class="muted">{t('viz_missing')}</p>
              : v.hdmi_connected === false
                ? <EmptyState icon="ico-plug-off" title={t('viz_hdmi_off')} sub={t('viz_hdmi_off_sub')} />
                : (
                <>
                  <Collapsible open={on}>
                    <Tabs compact active={v.engine} onChange={(id) => engine(id)}
                          items={[
                            { id: 'cava', label: t('viz_eng_cava') },
                            { id: 'glsl', label: t('viz_eng_glsl') + (v.glsl_available ? '' : ' ⚠'),
                              title: v.glsl_available ? '' : t('viz_glsl_missing') },
                          ]} />
                    {glsl && v.glsl_error && <p class="muted">{t('js_glsl_err')}{v.glsl_error}</p>}
                    {glsl
                      ? <ShaderPanel v={v} reload={reload} setMsg={setMsg} onPick={(id) => engine('glsl', id)} />
                      : <CavaControls v={v} reload={reload} setMsg={setMsg} />}
                  </Collapsible>
                  {!on && <p class="muted">{t('viz_off_hint')}</p>}
                </>)}
          {msg && <p class="muted">{msg}</p>}
        </div>

        <div class="card">
          <h2><i class="ico ico-brush"></i> {t('viz_studio_head')}</h2>
          <p class="muted">{t('viz_studio_note')}</p>
          <a class="btn sec" href={apiUrl('/studio')} target="_blank" style="text-align:center;text-decoration:none;">
            {t('viz_studio_btn')}
          </a>
        </div>
      </div>
    </section>
  );
}

// cava: preset list + inline editor.
function CavaControls({ v, reload, setMsg }) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(null);  // null closed, '' new, id edit
  const [form, setForm] = useState(null);

  const open = (id) => {
    const p = id ? (v.presets || []).find((x) => x.id === id) : null;
    const params = Object.assign({}, p ? p.params : (v.params || {}));
    setForm({
      label: p ? p.label : '',
      framerate: params.framerate, bar_width: params.bar_width,
      bar_spacing: params.bar_spacing, noise_reduction: params.noise_reduction,
      monstercat: !!params.monstercat, waves: !!params.waves,
      color: params.color, colors: (v.params || {}).colors || [],
      background: params.background || 'black', bg_colors: (v.params || {}).bg_colors || [],
    });
    setEditing(id || '');
  };
  const set = (k, val) => setForm((f) => ({ ...f, [k]: val }));
  const body = () => ({
    framerate: +form.framerate, bar_width: +form.bar_width,
    bar_spacing: +form.bar_spacing, noise_reduction: +form.noise_reduction,
    monstercat: form.monstercat, waves: form.waves, color: form.color,
    background: form.background,
  });

  const pick = async (name) => {
    try { setMsg((await apiPost('/api/viz/preset', { name })).message || ''); } catch { /* ignore */ }
    reload();
  };
  const apply = async () => {
    try { setMsg((await apiPost('/api/viz/params', body())).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    reload();
  };
  const save = async () => {
    try {
      const j = await apiPost('/api/viz/preset/save', { ...body(), id: editing || '', label: form.label });
      setMsg(j.message || '');
      if (j.ok) setEditing(null);
    } catch { setMsg(t('js_conn_error')); }
    reload();
  };
  const del = async () => {
    const p = (v.presets || []).find((x) => x.id === editing);
    if (!p || !confirm(t('js_vdel_pre') + p.label + t('js_vdel_suf'))) return;
    try {
      const j = await apiPost('/api/viz/preset/delete', { id: editing });
      setMsg(j.message || '');
      if (j.ok) setEditing(null);
    } catch { setMsg(t('js_conn_error')); }
    reload();
  };

  const slider = (k, label, min, max, step) => (
    <label class="vlabel">{label}: <b>{form[k]}</b>
      <input type="range" min={min} max={max} step={step} value={form[k]}
             onInput={(e) => set(k, e.currentTarget.value)} />
    </label>
  );

  return (
    <div>
      <div>
        {(v.presets || []).map((p) => (
          <div class="prow" key={p.id}>
            <button class={'btn ' + (p.id === v.preset ? '' : 'sec')} onClick={() => pick(p.id)}>
              {p.label}{p.id === v.preset ? ' ✓' : ''}
            </button>
            <button class="ebtn" title={t('viz_edit_title')} onClick={() => open(p.id)}>✎</button>
          </div>))}
      </div>
      <button class="btn sec" onClick={() => open(null)}>{t('viz_new_preset')}</button>

      {editing != null && form && (
        <div>
          <input value={form.label} maxLength={24} placeholder={t('viz_name_ph')} autocomplete="off"
                 onInput={(e) => set('label', e.currentTarget.value)} />
          {slider('framerate', t('viz_p_framerate'), 15, 60, 5)}
          {slider('bar_width', t('viz_p_bar_width'), 1, 12, 1)}
          {slider('bar_spacing', t('viz_p_bar_spacing'), 0, 5, 1)}
          {slider('noise_reduction', t('viz_p_noise'), 0, 100, 5)}
          <label class="vlabel">{t('viz_p_color')}
            <select value={form.color} onChange={(e) => set('color', e.currentTarget.value)}>
              {(form.colors || []).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label class="vlabel">{t('viz_p_background')}
            <select value={form.background} onChange={(e) => set('background', e.currentTarget.value)}>
              {(form.bg_colors || []).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label class="vlabel">
            <input type="checkbox" checked={form.monstercat} onChange={(e) => set('monstercat', e.currentTarget.checked)} /> {t('viz_p_monstercat')}
          </label>
          <label class="vlabel">
            <input type="checkbox" checked={form.waves} onChange={(e) => set('waves', e.currentTarget.checked)} /> {t('viz_p_waves')}
          </label>
          <div class="lrow">
            <button class="btn sec" onClick={apply}>{t('viz_apply')}</button>
            <button class="btn" onClick={save}>{t('viz_save')}</button>
          </div>
          {editing && <button class="btn sec" onClick={del}>{t('viz_delete')}</button>}
        </div>)}
    </div>
  );
}

// glsl: shader list + drag/drop or file-picker upload.
function ShaderPanel({ v, reload, setMsg, onPick }) {
  const { t } = useI18n();
  const [over, setOver] = useState(false);
  const [edit, setEdit] = useState(false);
  const fileRef = useRef(null);

  const setScale = async (s) => {
    try { setMsg((await apiPost('/api/viz/scale', { scale: s })).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    reload();
  };

  const upload = async (files) => {
    for (const f of files) {
      let source = '';
      try { source = await f.text(); } catch { continue; }
      try { setMsg((await apiPost('/api/viz/shader/upload', { name: f.name, source })).message || ''); }
      catch { setMsg(t('js_conn_error')); }
    }
    if (fileRef.current) fileRef.current.value = '';
    reload();
  };
  const del = async (id) => {
    const s = (v.shaders || []).find((x) => x.id === id);
    if (!s || !confirm(t('js_sdel_pre') + s.label + t('js_sdel_suf'))) return;
    try { setMsg((await apiPost('/api/viz/shader/delete', { id })).message || ''); }
    catch { setMsg(t('js_conn_error')); }
    reload();
  };

  return (
    <div>
      <div>
        {(v.shaders || []).map((s) => (
          <div class="prow" key={s.id}>
            <button class={'btn ' + (s.id === v.shader ? '' : 'sec')} onClick={() => onPick(s.id)}>
              {s.label}{s.id === v.shader ? ' ✓' : ''}
            </button>
            {s.id !== v.shader && (
              <button class="ebtn" title={t('sdel_title')} onClick={() => del(s.id)}>
                <i class="ico ico-trash"></i>
              </button>)}
          </div>))}
      </div>
      <div id="shaderDrop" class={over ? 'over' : ''}
           onClick={() => fileRef.current && fileRef.current.click()}
           onDragOver={(e) => { e.preventDefault(); setOver(true); }}
           onDragLeave={() => setOver(false)}
           onDrop={(e) => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files); }}>
        {t('shader_drop')}
      </div>
      <input ref={fileRef} type="file" accept=".frag,.glsl,.fs" multiple style="display:none;"
             onChange={(e) => upload(e.currentTarget.files)} />

      <button class="btn sec" onClick={() => setEdit(!edit)}>
        {t('viz_edit')}{v.scale && v.scale !== '1' ? ` (${v.scale}×)` : ''}
      </button>
      <Collapsible open={edit}>
        <div class="subhead muted">{t('viz_scale_head')}</div>
        <p class="muted small">{t('viz_scale_note')}</p>
        <div class="lrow">
          {(v.scales || ['1', '0.75', '0.5', '0.25']).map((s) => (
            <button key={s} class={'btn ' + (s === (v.scale || '1') ? '' : 'sec')}
                    onClick={() => setScale(s)}>
              {s}×{s === (v.scale || '1') ? ' ✓' : ''}
            </button>
          ))}
        </div>
      </Collapsible>
    </div>
  );
}
