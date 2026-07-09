import { useI18n } from '../i18n.jsx';
import { useStatus } from '../status.jsx';

// The status "shade" tucked behind the app sheet: Wi-Fi + Bluetooth at a glance.
// Revealed by pulling the sheet down (see PullSheet). Reads the shared /api/status
// poll, so it costs no extra requests.
export function StatusTray() {
  const { t } = useI18n();
  const { status } = useStatus();

  const ssid = (status && status.wifi_ssid) || '';
  const left = (status && status.pair_seconds_left) || 0;
  const connected = (status && status.connected) || [];
  const powered = !!(status && status.bt_powered);

  const bt = left > 0
    ? { text: t('st_bt_pairing') + ' ' + left + 's', dot: 'warn' }
    : connected.length
      ? { text: connected.map((d) => d.name).join(', '), dot: 'on' }
      : { text: powered ? t('st_bt_ready') : t('st_bt_off'), dot: powered ? '' : 'err' };

  return (
    <div class="statustray">
      <div class="st-row">
        <i class="ico ico-wifi"></i>
        <span class="st-label">Wi-Fi</span>
        <i class={'dot ' + (ssid ? 'on' : 'err')}></i>
        <span class="st-val">{ssid || t('st_wifi_off')}</span>
      </div>
      <div class="st-row">
        <i class="ico ico-bt"></i>
        <span class="st-label">Bluetooth</span>
        <i class={'dot ' + bt.dot}></i>
        <span class="st-val">{bt.text}</span>
      </div>
    </div>
  );
}
