import { useState } from 'preact/hooks';
import { useStatus } from '../status.jsx';
import { useI18n } from '../i18n.jsx';
import { apiPost } from '../api.js';
import { navigate, useRoute } from '../router.jsx';

export function Header() {
  const { status, refresh } = useStatus();
  const { t, device } = useI18n();
  const route = useRoute();
  const [busy, setBusy] = useState(false);

  const left = (status && status.pair_seconds_left) || 0;
  const onSettings = route === '/settings';

  const pair = async () => {
    setBusy(true);
    try { await apiPost('/api/pair'); } catch { /* ignore */ }
    setBusy(false);
    refresh();
  };

  return (
    <header class="top">
      <h1><a class="brand" href="#/">{device}</a></h1>
      <div class="topbtns">
        <button class={'iconbtn' + (left > 0 ? ' active' : '')} disabled={busy}
                onClick={pair} title={t('bt_button')}>
          <i class="ico ico-bt" aria-hidden="true"></i>
          <span>{left > 0 ? left + 's' : t('pair_short')}</span>
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
