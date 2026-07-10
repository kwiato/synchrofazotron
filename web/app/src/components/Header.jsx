import { useState } from 'preact/hooks';
import { useStatus } from '../status.jsx';
import { useI18n } from '../i18n.jsx';
import { apiPost } from '../api.js';
import { goHome, navigate, useRoute } from '../router.jsx';
import { RingMark } from './ConsoleLogo.jsx';

export function Header() {
  const { status, refresh } = useStatus();
  const { t, device } = useI18n();
  const route = useRoute();
  const [busy, setBusy] = useState(false);

  const left = (status && status.pair_seconds_left) || 0;
  const onSettings = route === '/settings';
  const btName = (status && status.connected && status.connected[0] && status.connected[0].name) || '';

  const pair = async () => {
    setBusy(true);
    try { await apiPost('/api/pair'); } catch { /* ignore */ }
    setBusy(false);
    refresh();
  };

  return (
    <header class="top">
      <h1 class="brand">
        {/* homepage: also forces the Now tab (href alone wouldn't switch it) */}
        <a href="#/" aria-label={device} onClick={(e) => { e.preventDefault(); goHome(); }}>
          <RingMark class="brand-mark" />
          <span class="brand-name">{device}</span>
        </a>
      </h1>
      <div class="topbtns">
        <button class={'iconbtn' + (left > 0 || btName ? ' active' : '')} disabled={busy}
                onClick={pair} title={t('bt_button')} aria-label={t('bt_button')}>
          <i class="ico ico-bt" aria-hidden="true"></i>
          {left > 0 && <span class="lbl">{left}s</span>}
        </button>
        <button class={'iconbtn' + (onSettings ? ' active' : '')}
                onClick={() => navigate(onSettings ? '/' : '/settings')}
                title={onSettings ? t('back_to_panel') : t('settings_link_title')}
                aria-label={t('settings_link_title')}>
          <i class="ico ico-cog" aria-hidden="true"></i>
        </button>
      </div>
    </header>
  );
}
