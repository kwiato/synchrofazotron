import { useState } from 'preact/hooks';
import { useStatus } from '../status.jsx';
import { useI18n } from '../i18n.jsx';
import { apiPost } from '../api.js';
import { primary, srcSub } from '../util.js';
import { Eq } from './Eq.jsx';

// Bottom player bar + the expandable sources sheet. Ported from common.js;
// the sheet open/closed state is now local component state instead of a class
// toggle on a DOM node.
export function PlayerBar() {
  const { status, refresh } = useStatus();
  const { t } = useI18n();
  const [open, setOpen] = useState(false);

  const p = primary(status);
  const ctrlOff = !(p && p.controllable && p.id);
  const sources = (status && status.sources) || [];
  const owners = (status && status.dac_owners) || [];

  const ctrl = async (id, action) => {
    try {
      await apiPost('/api/control', { source: id, action: action || 'toggle' });
    } catch { /* ignore */ }
    setTimeout(refresh, 500);
  };
  const ctrlPrimary = (action) => { if (!ctrlOff) ctrl(p.id, action); };

  return (
    <div class="playerbar">
      <div class={'pbwrap' + (open ? ' open' : '')}>
        <div class="sheet">
          <div class="sheet-head">{t('sheet_sources')}</div>
          <div>
            {sources.length === 0
              ? <p class="muted">{t('js_silence')}</p>
              : sources.map((x) => {
                  const off = !(x.controllable && x.id);
                  return (
                    <div class="srow" key={x.id || x.name}>
                      <div class="info">
                        <Eq n={3} on={x.playing} />{' '}
                        <b>{x.name}</b> — {x.state}
                        {x.detail && <div class="det">{x.detail}</div>}
                      </div>
                      <button class={'tbtn' + (x.playing ? ' playing' : '')}
                              disabled={off} title={off ? t('js_ctrl_hint') : ''}
                              onClick={() => !off && ctrl(x.id)}>
                        {x.playing ? '⏸' : '▶'}
                      </button>
                    </div>
                  );
                })}
          </div>
          <p class="muted small">
            {owners.length
              ? <>{t('js_dac_owner')}{owners.map((o, i) => (
                  <span key={i}>{i ? ', ' : ''}<b>{o.label}</b>{o.running ? '' : ' ' + t('js_dac_hold')}</span>
                ))}</>
              : t('js_dac_free')}
          </p>
          <p class="muted small">{t('sources_note')}</p>
        </div>

        <div class="inner">
          <button class="iconbtn arrow" onClick={() => setOpen((o) => !o)}
                  title={t('sheet_sources')} aria-label={t('sheet_sources')}>
            <i class="ico ico-chev" aria-hidden="true"></i>
          </button>
          <Eq n={3} on={!!(p && p.playing)} />
          <div class="pb-info">
            <div class="pb-title">{p ? (p.detail || p.name) : t('js_silence')}</div>
            <div class="pb-sub muted">{p ? srcSub(p) : ''}</div>
          </div>
          <button class="pbskip" disabled={ctrlOff} aria-label="prev"
                  onClick={() => ctrlPrimary('prev')}>
            <i class="ico ico-prev" aria-hidden="true"></i>
          </button>
          <button class="playbtn" disabled={ctrlOff} title={ctrlOff ? t('js_ctrl_hint') : ''}
                  onClick={() => ctrlPrimary('toggle')}>
            <i class={'ico ico-lg ' + (p && p.playing ? 'ico-pause' : 'ico-play')} aria-hidden="true"></i>
          </button>
          <button class="pbskip" disabled={ctrlOff} aria-label="next"
                  onClick={() => ctrlPrimary('next')}>
            <i class="ico ico-next" aria-hidden="true"></i>
          </button>
        </div>
      </div>
    </div>
  );
}
