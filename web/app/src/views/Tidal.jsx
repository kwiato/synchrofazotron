import { useCallback, useEffect, useState } from 'preact/hooks';
import { useI18n } from '../i18n.jsx';
import { useToast } from '../components/Toast.jsx';
import { apiGet, apiPost } from '../api.js';
import { radioFx } from '../prefs.js';
import { pendingStart, pendingClear } from '../pending.js';
import { List, BackSlot, navKey } from './Radio.jsx';

// TIDAL browser: one SlimBrowse tree proxied by the panel (/api/lms/tidal).
// Unlike radio there is no phone-direct path — the account lives in LMS, so
// all browsing goes through the device. Search lives inside the tree: drilling
// into a search node shows an input and re-browses with the term.
export function TidalTab() {
  const { t } = useI18n();
  const toast = useToast();
  const [stack, setStack] = useState([]);   // [{title, item_id, searchable}]
  const [q, setQ] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const top = stack[stack.length - 1];
  const searching = !!(top && top.searchable);

  const load = useCallback(async () => {
    if (searching && !q.trim()) { setData({ items: [] }); return; }
    setLoading(true);
    try {
      setData(await apiGet('/api/lms/tidal/browse'
        + `?item_id=${encodeURIComponent((top && top.item_id) || '')}`
        + (searching ? `&search=${encodeURIComponent(q)}` : '')));
    } catch {
      setData({ items: [], error: 'lms' });
    }
    setLoading(false);
  }, [stack, q, searching]);

  // entering/leaving a search node resets the term; debounce live typing
  useEffect(() => { setQ(''); }, [stack.length]);
  useEffect(() => {
    const id = setTimeout(load, searching && q ? 400 : 0);
    return () => clearTimeout(id);
  }, [load]);

  const onOpen = (it) => setStack([...stack, {
    title: it.title, item_id: it.item_id || '', searchable: !!it.searchable,
  }]);
  const onPlay = async (it) => {
    pendingStart();                       // feedback ring on the play button
    try { await apiPost('/api/lms/tidal/play', { item_id: it.item_id }); }
    catch { pendingClear(); toast(t('radio_play_err')); }
  };
  const onStar = async (it) => {
    try { await apiPost('/api/lms/favorites/add', it.fav); toast(t('radio_added')); }
    catch { /* ignore */ }
  };

  const fx = radioFx();
  return (
    <section>
      <div class="lms">
        {searching && (
          <input class="in lms-search" type="search" inputMode="search"
                 placeholder={top.title || t('tidal_search_ph')} value={q}
                 onInput={(e) => setQ(e.currentTarget.value)} />
        )}
        <BackSlot stack={stack} fx={fx} onBack={() => setStack(stack.slice(0, -1))}
                  rootLabel={t('tab_tidal')} />
        <div key={fx ? navKey(stack, loading) : 'k'} class={fx ? 'lms-in' : ''}>
          <List data={data} loading={loading} fx={fx}
                onOpen={onOpen} onPlay={onPlay} onStar={onStar} />
        </div>
      </div>
    </section>
  );
}
