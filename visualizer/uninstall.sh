#!/bin/bash
# Synchrofazotron visualizer — full uninstall (sources go straight back to the DAC).
#   curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/visualizer/uninstall.sh | sudo bash
set -euo pipefail

DAC_PCM="hw:CARD=BossDAC,DEV=0"

echo "==> Stopping and removing services"
systemctl disable --now pistream-hdmi-watch.service 2>/dev/null || true
systemctl stop pistream-visualizer.service 2>/dev/null || true
rm -f /etc/systemd/system/pistream-visualizer.service \
      /etc/systemd/system/pistream-hdmi-watch.service
rm -rf /opt/pistream-visualizer
systemctl daemon-reload
systemctl start getty@tty1 2>/dev/null || true

echo "==> Removing the 'pistream' device from /etc/asound.conf"
sed -i '/# PISTREAM-VIZ BEGIN/,/# PISTREAM-VIZ END/d' /etc/asound.conf 2>/dev/null || true

echo "==> Repointing sources back at $DAC_PCM"
if [[ -f /etc/default/squeezelite ]]; then
  if grep -qE '^#?SL_SOUNDCARD=' /etc/default/squeezelite; then
    sed -i -E "s|^#?SL_SOUNDCARD=.*|SL_SOUNDCARD=\"$DAC_PCM\"|" /etc/default/squeezelite
  else
    sed -i -E "s|-o [^ '\"]+|-o $DAC_PCM|" /etc/default/squeezelite
  fi
fi
SP_CONF=/usr/local/etc/shairport-sync.conf
[[ -f $SP_CONF ]] || SP_CONF=/etc/shairport-sync.conf
if [[ -f $SP_CONF ]]; then
  sed -i -E "s|^([[:space:]]*)output_device = \".*\";|\1output_device = \"$DAC_PCM\";|" "$SP_CONF"
fi
cat > /etc/systemd/system/bluealsa-aplay.service.d/override.conf <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/bluealsa-aplay -S -d $DAC_PCM
EOF

echo "==> Disabling snd-aloop at boot"
rm -f /etc/modules-load.d/pistream-visualizer.conf /etc/modprobe.d/pistream-aloop.conf
# rmmod only after restarting the sources (they may still hold the loopback)

systemctl daemon-reload
systemctl restart squeezelite 2>/dev/null || true
systemctl restart shairport-sync 2>/dev/null || true
systemctl restart bluealsa-aplay 2>/dev/null || true
modprobe -r snd-aloop 2>/dev/null || echo "   (snd-aloop will disappear on the next reboot)"

echo "==> Done — the audio path goes straight to the DAC again. cava left installed (apt remove cava if unwanted)."
