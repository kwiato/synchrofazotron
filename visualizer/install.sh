#!/bin/bash
# PiStream visualizer — instalacja / aktualizacja.
#
#   curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/visualizer/install.sh | sudo bash
#
# Co robi:
#   1) snd-aloop (wirtualna pętla audio) ładowany przy boocie
#   2) urządzenie ALSA "pistream" = DAC + kopia do pętli (blok w /etc/asound.conf)
#   3) przepina squeezelite / shairport-sync / bluealsa-aplay na "pistream" (z backupami)
#   4) cava czytająca z pętli, wyświetlana na HDMI (tty1)
#   5) watcher: HDMI wpięte -> wizualizer startuje; wypięte -> gaśnie
# Odwrócenie wszystkiego: uninstall.sh z tego samego katalogu repo.
set -euo pipefail

REPO="${PISTREAM_REPO:-kwiato/synchrofazotron}"
BRANCH="${PISTREAM_BRANCH:-main}"
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH/visualizer"
FILES=(asound-tee.conf cava.conf pistream-visualizer.service pistream-hdmi-watch.service hdmi-watch.sh)
DEST=/opt/pistream-visualizer
DAC_PCM="hw:CARD=BossDAC,DEV=0"   # do czego wracamy przy uninstallu
STAMP="$(date +%Y%m%d-%H%M%S)"

SRC_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo .)"
if [[ "$(basename -- "$0")" != "install.sh" || ! -f "$SRC_DIR/asound-tee.conf" ]]; then
  echo "==> Pobieram $REPO@$BRANCH z GitHuba"
  SRC_DIR="$(mktemp -d)"
  trap 'rm -rf "$SRC_DIR"' EXIT
  for f in "${FILES[@]}"; do
    curl -fsSL "$RAW/$f" -o "$SRC_DIR/$f"
  done
fi

echo "==> Instalacja cava"
if ! command -v cava >/dev/null 2>&1; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y cava
fi

echo "==> Moduł snd-aloop (pętla audio)"
echo snd-aloop > /etc/modules-load.d/pistream-visualizer.conf
# index=7: pętla nie może podebrać numeru karty 0 DAC-owi
echo "options snd-aloop index=7 pcm_substreams=2" > /etc/modprobe.d/pistream-aloop.conf
modprobe snd-aloop index=7 pcm_substreams=2 2>/dev/null || true
grep -q Loopback /proc/asound/cards || { echo "BŁĄD: snd-aloop nie wstał"; exit 1; }

echo "==> Urządzenie ALSA 'pistream' (DAC + kopia do pętli)"
touch /etc/asound.conf
cp /etc/asound.conf "/etc/asound.conf.bak.$STAMP"
sed -i '/# PISTREAM-VIZ BEGIN/,/# PISTREAM-VIZ END/d' /etc/asound.conf
cat "$SRC_DIR/asound-tee.conf" >> /etc/asound.conf

echo "==> Przepinam źródła audio na 'pistream'"
# squeezelite: -o <cokolwiek>  ->  -o pistream
if [[ -f /etc/default/squeezelite ]]; then
  cp /etc/default/squeezelite "/etc/default/squeezelite.bak.$STAMP"
  sed -i -E "s|-o [^ ']+|-o pistream|" /etc/default/squeezelite
fi
# shairport-sync: output_device
SP_CONF=/usr/local/etc/shairport-sync.conf
[[ -f $SP_CONF ]] || SP_CONF=/etc/shairport-sync.conf
if [[ -f $SP_CONF ]]; then
  cp "$SP_CONF" "$SP_CONF.bak.$STAMP"
  sed -i -E 's|^([[:space:]]*)output_device = ".*";|\1output_device = "pistream";|' "$SP_CONF"
fi
# bluealsa-aplay: override systemd
install -d /etc/systemd/system/bluealsa-aplay.service.d
cat > /etc/systemd/system/bluealsa-aplay.service.d/override.conf <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/bluealsa-aplay -S -d pistream
EOF

echo "==> Pliki wizualizera i usługi"
install -d "$DEST"
install -m 0644 "$SRC_DIR/cava.conf" "$DEST/cava.conf"
install -m 0755 "$SRC_DIR/hdmi-watch.sh" "$DEST/hdmi-watch.sh"
install -m 0644 "$SRC_DIR/pistream-visualizer.service" /etc/systemd/system/
install -m 0644 "$SRC_DIR/pistream-hdmi-watch.service" /etc/systemd/system/

systemctl daemon-reload
systemctl restart squeezelite 2>/dev/null || true
systemctl restart shairport-sync 2>/dev/null || true
systemctl restart bluealsa-aplay 2>/dev/null || true
systemctl enable --now pistream-hdmi-watch.service
systemctl restart pistream-hdmi-watch.service

echo
echo "==> Gotowe. Backupy configów: *.bak.$STAMP"
echo "    HDMI wpięte  -> wizualizer wstaje sam (do ~5 s)"
echo "    Konsola logowania na HDMI wróci po: systemctl stop pistream-hdmi-watch pistream-visualizer && systemctl start getty@tty1"
echo "    Test bez HDMI: puść muzykę i sprawdź 'arecord -D plughw:Loopback,1,0 -f S16_LE -d 1 /tmp/t.wav'"
