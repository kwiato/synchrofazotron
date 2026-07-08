import { useEffect, useRef, useState } from 'preact/hooks';
import { useI18n } from '../i18n.jsx';
import { apiGet, apiPost } from '../api.js';

// "Add a network" modal — add by SSID/key, or scan and pick. onAdded(message)
// lets the parent surface the result and reload the saved list.
export function WifiModal({ open, onClose, onAdded }) {
  const { t } = useI18n();
  const [ssid, setSsid] = useState('');
  const [key, setKey] = useState('');
  const [scan, setScan] = useState(null);   // null = not scanned yet
  const [scanning, setScanning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const ssidRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    setMsg('');
    setScan(null);
    const id = setTimeout(() => ssidRef.current && ssidRef.current.focus(), 0);
    return () => clearTimeout(id);
  }, [open]);

  if (!open) return null;

  const add = async () => {
    setBusy(true);
    setMsg(t('js_saving'));
    try {
      const j = await apiPost('/api/wifi/add', { ssid, key });
      if (j.ok) {
        setSsid('');
        setKey('');
        onAdded(j.message || 'OK');
        onClose();
      } else {
        setMsg(j.message || t('js_error'));
      }
    } catch { setMsg(t('js_conn_error')); }
    setBusy(false);
  };

  const doScan = async () => {
    setScanning(true);
    try { setScan((await apiGet('/api/wifi/scan')).networks || []); }
    catch { setMsg(t('js_scan_fail')); }
    setScanning(false);
  };

  return (
    <div class="overlay open" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div class="modal">
        <h2><i class="ico ico-plus"></i> {t('wifi_add_head')}</h2>
        <p class="muted">{t('wifi_add_note')}</p>
        <input ref={ssidRef} value={ssid} placeholder={t('wifi_ssid_ph')} autocomplete="off"
               onInput={(e) => setSsid(e.currentTarget.value)} />
        <input type="password" value={key} placeholder={t('wifi_key_ph')} autocomplete="new-password"
               onInput={(e) => setKey(e.currentTarget.value)} />
        <button class="btn" disabled={busy} onClick={add}>{t('wifi_save_btn')}</button>
        <button class="btn sec" disabled={scanning} onClick={doScan}>
          {scanning ? t('js_scanning') : t('wifi_scan_btn')}
        </button>
        <div>
          {scan && (scan.length
            ? scan.map((n) => (
                <button class="btn sec netbtn" key={n.ssid} onClick={() => setSsid(n.ssid)}>
                  {n.ssid} <span class="muted">{n.signal} dBm</span>
                </button>))
            : <p class="muted">{t('js_scan_none')}</p>)}
        </div>
        {msg && <p class="muted">{msg}</p>}
        <button class="btn sec" onClick={onClose}>{t('modal_cancel')}</button>
      </div>
    </div>
  );
}
