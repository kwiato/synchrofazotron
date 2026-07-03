#!/bin/bash
# PiStream visualizer — pełne odwrócenie instalacji (powrót źródeł wprost na DAC).
#   curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/visualizer/uninstall.sh | sudo bash
set -euo pipefail

DAC_PCM="hw:CARD=BossDAC,DEV=0"

echo "==> Zatrzymuję i usuwam usługi"
systemctl disable --now pistream-hdmi-watch.service 2>/dev/null || true
systemctl stop pistream-visualizer.service 2>/dev/null || true
rm -f /etc/systemd/system/pistream-visualizer.service \
      /etc/systemd/system/pistream-hdmi-watch.service
rm -rf /opt/pistream-visualizer
systemctl daemon-reload
systemctl start getty@tty1 2>/dev/null || true

echo "==> Usuwam urządzenie 'pistream' z /etc/asound.conf"
sed -i '/# PISTREAM-VIZ BEGIN/,/# PISTREAM-VIZ END/d' /etc/asound.conf 2>/dev/null || true

echo "==> Przepinam źródła z powrotem na $DAC_PCM"
if [[ -f /etc/default/squeezelite ]]; then
  sed -i -E "s|-o [^ ']+|-o $DAC_PCM|" /etc/default/squeezelite
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

echo "==> Wyłączam snd-aloop przy boocie"
rm -f /etc/modules-load.d/pistream-visualizer.conf /etc/modprobe.d/pistream-aloop.conf
# rmmod dopiero po restarcie źródeł (mogą trzymać pętlę)

systemctl daemon-reload
systemctl restart squeezelite 2>/dev/null || true
systemctl restart shairport-sync 2>/dev/null || true
systemctl restart bluealsa-aplay 2>/dev/null || true
modprobe -r snd-aloop 2>/dev/null || echo "   (snd-aloop zniknie przy najbliższym reboocie)"

echo "==> Gotowe — tor audio z powrotem bezpośrednio na DAC. cava zostawiona (apt remove cava, jeśli zbędna)."
