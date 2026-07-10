import { useCallback, useEffect, useState } from 'preact/hooks';
import { useI18n } from '../i18n.jsx';
import { useToast } from '../components/Toast.jsx';
import { apiGet, apiPost } from '../api.js';
import { lmsIcon, IS_APP } from '../host.js';
import { tuneinRoot, tuneinBrowse, tuneinSearch } from '../tunein.js';
import { Tabs } from '../components/Tabs.jsx';
import { EmptyState } from '../components/EmptyState.jsx';

// Radio browser. Two data paths into the same list UI:
//   * app shell — the phone browses TuneIn directly (tunein.js) and only sends
//     "play this URL" / favorites to the device; falls back to the LMS path if
//     TuneIn is unreachable.
//   * web build — everything over the panel's LMS proxy (browser CORS rules
//     block TuneIn's API there).
// TuneIn is a tree, so Browse and Favorites each keep a navigation stack
// (folders push, back pops); Search is a flat query. A station row plays on
// tap and can be starred into favorites (stored in LMS — shared with the web).

export function RadioTab() {
  const { t } = useI18n();
  const [mode, setMode] = useState('browse');   // browse | search | fav

  return (
    <section>
      <Tabs active={mode} onChange={setMode}
            items={[
              { id: 'browse', label: t('radio_browse') },
              { id: 'search', label: t('radio_search') },
              { id: 'fav', label: t('radio_fav') },
            ]} />
      {mode === 'browse' && <Browser kind="browse" />}
      {mode === 'search' && <Search />}
      {mode === 'fav' && <Browser kind="fav" />}
    </section>
  );
}

// Shared list renderer for a normalized {items:[{title,icon,playable,browsable,
// item_id,fav,id,url,header}]} payload. onOpen(item) drills in, onPlay(item)
// plays. `direct` marks TuneIn-direct items whose icons are absolute CDN URLs
// (no panel proxy needed).
function List({ data, loading, direct, onOpen, onPlay, onStar, onRemove }) {
  const { t } = useI18n();
  if (loading && !data) return <p class="muted lms-note">{t('radio_loading')}</p>;
  if (data && data.error === 'lms') {
    return <EmptyState icon="ico-plug-off" title={t('radio_unavailable')} />;
  }
  const items = (data && data.items) || [];
  if (!items.length) {
    return <EmptyState title={onRemove ? t('radio_fav_empty') : t('radio_empty')} />;
  }
  return (
    <div class="lms-list">
      {items.map((it, i) => {
        if (it.header) return <div key={'h' + i} class="lms-group muted">{it.title}</div>;
        const icon = direct ? it.icon : lmsIcon(it.icon);
        const act = () => (it.browsable ? onOpen(it) : it.playable && onPlay(it));
        return (
          <div key={it.item_id || it.id || it.url || i} class="lms-row" role="button" tabIndex={0}
               onClick={act} onKeyDown={(e) => e.key === 'Enter' && act()}>
            {icon
              ? <img class="lms-ico" src={icon} loading="lazy" alt="" />
              : <span class="lms-ico lms-ico-ph">{it.browsable ? '▸' : '♪'}</span>}
            <span class="lms-title">{it.title}</span>
            {onStar && it.fav && (
              <button class="lms-act" title={t('radio_fav')}
                      onClick={(e) => { e.stopPropagation(); onStar(it); }}>☆</button>
            )}
            {onRemove && (
              <button class="lms-act" title={t('radio_removed')}
                      onClick={(e) => { e.stopPropagation(); onRemove(it); }}>🗑</button>
            )}
            {it.browsable && <span class="lms-chev">›</span>}
          </div>
        );
      })}
    </div>
  );
}

// Plays a TuneIn-direct station: the device just gets the stream URL.
const playUrl = (it) => apiPost('/api/lms/playurl', { url: it.url, title: it.title });

// kind 'browse' walks TuneIn (direct or via LMS verbs); kind 'fav' walks the
// LMS favorites (id) — favorites always live on the device.
function Browser({ kind }) {
  const { t } = useI18n();
  const toast = useToast();
  const [stack, setStack] = useState([]);       // [{title, url | verb+item_id | id}]
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [useLms, setUseLms] = useState(!IS_APP);
  const direct = kind === 'browse' && !useLms;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const top = stack[stack.length - 1];
      let d;
      if (kind === 'fav') {
        d = await apiGet('/api/lms/favorites'
          + (top ? `?item_id=${encodeURIComponent(top.id)}` : ''));
      } else if (direct) {
        d = { items: top ? await tuneinBrowse(top.url) : await tuneinRoot() };
      } else if (!top) {
        d = await apiGet('/api/lms/radio');           // root = TuneIn top menu
      } else {
        d = await apiGet(`/api/lms/radio/browse?verb=${encodeURIComponent(top.verb)}`
          + `&item_id=${encodeURIComponent(top.item_id || '')}`);
      }
      setData(d);
    } catch {
      if (direct) { setStack([]); setUseLms(true); }  // retry over the LMS path
      else setData({ items: [], error: 'lms' });
    }
    setLoading(false);
  }, [kind, stack, direct]);

  useEffect(() => { load(); }, [load]);

  const currentVerb = () => {
    for (let i = stack.length - 1; i >= 0; i--) if (stack[i].verb) return stack[i].verb;
    return '';
  };

  const onOpen = (it) => {
    if (kind === 'fav') { setStack([...stack, { title: it.title, id: it.id }]); return; }
    if (direct) { setStack([...stack, { title: it.title, url: it.url }]); return; }
    // root items carry their own verb; deeper folders inherit the current verb.
    const verb = it.verb || currentVerb();
    setStack([...stack, { title: it.title, verb, item_id: it.item_id || '' }]);
  };

  const onPlay = async (it) => {
    try {
      if (kind === 'fav') await apiPost('/api/lms/favorites/play', { id: it.id });
      else if (direct) await playUrl(it);
      else await apiPost('/api/lms/radio/play', { verb: currentVerb(), item_id: it.item_id });
    } catch { toast(t('radio_play_err')); }
  };

  const onStar = async (it) => {
    try { await apiPost('/api/lms/favorites/add', it.fav); toast(t('radio_added')); }
    catch { /* ignore */ }
  };

  const onRemove = kind === 'fav' ? async (it) => {
    try { await apiPost('/api/lms/favorites/remove', { id: it.id }); toast(t('radio_removed')); load(); }
    catch { /* ignore */ }
  } : null;

  return (
    <div class="lms">
      {stack.length > 0 && (
        <button class="lms-back" onClick={() => setStack(stack.slice(0, -1))}>
          ‹ {stack.length > 1 ? stack[stack.length - 2].title : t(kind === 'fav' ? 'radio_fav' : 'radio_browse')}
        </button>
      )}
      <List data={data} loading={loading} direct={direct} onOpen={onOpen} onPlay={onPlay}
            onStar={kind === 'fav' ? null : onStar} onRemove={onRemove} />
    </div>
  );
}

function Search() {
  const { t } = useI18n();
  const toast = useToast();
  const [q, setQ] = useState('');
  const [stack, setStack] = useState([]);   // folders drilled into from results
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [useLms, setUseLms] = useState(!IS_APP);
  const direct = !useLms;

  const load = useCallback(async () => {
    if (!q.trim()) { setData(null); return; }
    setLoading(true);
    try {
      const top = stack[stack.length - 1];
      let d;
      if (direct) {
        d = { items: top ? await tuneinBrowse(top.url) : await tuneinSearch(q) };
      } else {
        d = top
          ? await apiGet(`/api/lms/radio/browse?verb=search&item_id=${encodeURIComponent(top.item_id)}`)
          : await apiGet(`/api/lms/radio/search?q=${encodeURIComponent(q)}`);
      }
      setData(d);
    } catch {
      if (direct) { setStack([]); setUseLms(true); }  // retry over the LMS path
      else setData({ items: [], error: 'lms' });
    }
    setLoading(false);
  }, [q, stack, direct]);

  // New query resets the drill-down; debounce so we do not hammer TuneIn.
  useEffect(() => { setStack([]); }, [q]);
  useEffect(() => { const id = setTimeout(load, stack.length ? 0 : 400); return () => clearTimeout(id); }, [load]);

  const onOpen = (it) => setStack([...stack,
    direct ? { title: it.title, url: it.url } : { title: it.title, item_id: it.item_id }]);
  const onPlay = async (it) => {
    try {
      if (direct) await playUrl(it);
      else await apiPost('/api/lms/radio/play', { verb: 'search', item_id: it.item_id });
    } catch { toast(t('radio_play_err')); }
  };
  const onStar = async (it) => {
    try { await apiPost('/api/lms/favorites/add', it.fav); toast(t('radio_added')); }
    catch { /* ignore */ }
  };

  return (
    <div class="lms">
      <input class="in lms-search" type="search" inputMode="search"
             placeholder={t('radio_search_ph')} value={q}
             onInput={(e) => setQ(e.currentTarget.value)} />
      {stack.length > 0 && (
        <button class="lms-back" onClick={() => setStack(stack.slice(0, -1))}>
          ‹ {stack.length > 1 ? stack[stack.length - 2].title : t('radio_search')}
        </button>
      )}
      <List data={data} loading={loading} direct={direct} onOpen={onOpen} onPlay={onPlay} onStar={onStar} />
    </div>
  );
}
