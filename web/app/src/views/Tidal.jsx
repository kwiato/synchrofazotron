import { useCallback, useEffect, useRef, useState } from 'preact/hooks';
import { useI18n } from '../i18n.jsx';
import { useToast } from '../components/Toast.jsx';
import { apiGet, apiPost } from '../api.js';
import { radioFx } from '../prefs.js';
import { pendingStart, pendingClear } from '../pending.js';
import { List, BackSlot, navKey } from './Radio.jsx';

// TIDAL browser: one SlimBrowse tree proxied by the panel (/api/lms/tidal).
// Unlike radio there is no phone-direct path — the account lives in LMS, so
// all browsing goes through the device. The search box sits on top: typing
// queries the tree's search node (its item_id is lifted from the root menu and
// the node itself is hidden from the list); clearing the box returns to the
// browse view, each side keeping its own navigation stack. Albums and
// playlists carry a play-all button next to the drill-in row.
export function TidalTab() {
  const { t } = useI18n();
  const toast = useToast();
  const [q, setQ] = useState('');
  const searchId = useRef('');                  // item_id of the root Search node
  const [bstack, setBstack] = useState([]);     // browse drill-down
  const [sstack, setSstack] = useState([]);     // search-results drill-down
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const inSearch = !!q.trim();
  const stack = inSearch ? sstack : bstack;
  const setStack = inSearch ? setSstack : setBstack;
  const top = stack[stack.length - 1];

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // typing can outrun the initial root fetch — lift the search node's
      // item_id from the root menu on demand
      if (inSearch && !searchId.current) {
        const root = await apiGet('/api/lms/tidal/browse?item_id=');
        const s = (root.items || []).find((i) => i.searchable);
        if (s) searchId.current = s.item_id;
        if (!searchId.current) { setData({ items: [] }); setLoading(false); return; }
      }
      let url;
      if (inSearch && !top) {
        // fresh query hits the search node; deeper levels reuse the LMS-cached
        // search context, so only item_id is needed there
        url = `/api/lms/tidal/browse?item_id=${encodeURIComponent(searchId.current)}`
          + `&search=${encodeURIComponent(q.trim())}`;
      } else {
        url = `/api/lms/tidal/browse?item_id=${encodeURIComponent((top && top.item_id) || '')}`;
      }
      const d = await apiGet(url);
      const items = (d.items || []).filter((i) => !i.searchable);
      if (!inSearch && !top) {
        const s = (d.items || []).find((i) => i.searchable);
        if (s) searchId.current = s.item_id;
      }
      setData({ ...d, items });
    } catch {
      setData({ items: [], error: 'lms' });
    }
    setLoading(false);
  }, [inSearch, stack, q]);

  // a new query resets the search drill-down; live typing is debounced
  useEffect(() => { setSstack([]); }, [q]);
  useEffect(() => {
    const id = setTimeout(load, inSearch && !stack.length ? 400 : 0);
    return () => clearTimeout(id);
  }, [load]);

  const onOpen = (it) => setStack([...stack, { title: it.title, item_id: it.item_id || '' }]);
  const play = async (it) => {
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
        <input class="in lms-search" type="search" inputMode="search"
               placeholder={t('tidal_search_ph')} value={q}
               onInput={(e) => setQ(e.currentTarget.value)} />
        <BackSlot stack={stack} fx={fx} onBack={() => setStack(stack.slice(0, -1))}
                  rootLabel={inSearch ? t('radio_search') : t('tab_tidal')} />
        <div key={fx ? navKey(stack, loading) + (inSearch ? 's' : 'b') : 'k'}
             class={fx ? 'lms-in' : ''}>
          <List data={data} loading={loading} fx={fx}
                onOpen={onOpen} onPlay={play} onPlayAll={play} onStar={onStar} />
        </div>
      </div>
    </section>
  );
}
