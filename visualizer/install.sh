#!/bin/bash
# Synchrofazotron visualizer — install / update.
#
#   curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/visualizer/install.sh | sudo bash
#
# What it does:
#   1) snd-aloop (virtual audio loopback) loaded at boot
#   2) ALSA device "pistream" = DAC + a copy into the loopback (block in /etc/asound.conf)
#   3) repoints squeezelite / shairport-sync / bluealsa-aplay at "pistream" (with backups)
#   4) cava reading from the loopback, displayed on HDMI (tty1)
#   5) watcher: HDMI plugged in -> visualizer starts; unplugged -> it goes dark
# To undo everything: uninstall.sh from the same repo directory.
set -euo pipefail

REPO="${PISTREAM_REPO:-kwiato/synchrofazotron}"
BRANCH="${PISTREAM_BRANCH:-main}"
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH/visualizer"
FILES=(asound-tee.conf cava.conf pistream-visualizer.service pistream-hdmi-watch.service hdmi-watch.sh)
DEST=/opt/pistream-visualizer
DAC_PCM="hw:CARD=BossDAC,DEV=0"   # what uninstall reverts to
STAMP="$(date +%Y%m%d-%H%M%S)"

SRC_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo .)"
if [[ "$(basename -- "$0")" != "install.sh" || ! -f "$SRC_DIR/asound-tee.conf" ]]; then
  echo "==> Downloading $REPO@$BRANCH from GitHub"
  SRC_DIR="$(mktemp -d)"
  trap 'rm -rf "$SRC_DIR"' EXIT
  for f in "${FILES[@]}"; do
    curl -fsSL "$RAW/$f" -o "$SRC_DIR/$f"
  done
fi

echo "==> Installing cava"
if ! command -v cava >/dev/null 2>&1; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y cava
fi

echo "==> snd-aloop module (audio loopback)"
echo snd-aloop > /etc/modules-load.d/pistream-visualizer.conf
# index=7: the loopback must not steal card number 0 from the DAC
echo "options snd-aloop index=7 pcm_substreams=2" > /etc/modprobe.d/pistream-aloop.conf
modprobe snd-aloop index=7 pcm_substreams=2 2>/dev/null || true
grep -q Loopback /proc/asound/cards || { echo "ERROR: snd-aloop did not come up"; exit 1; }

echo "==> ALSA device 'pistream' (DAC + copy into the loopback)"
touch /etc/asound.conf
cp /etc/asound.conf "/etc/asound.conf.bak.$STAMP"
sed -i '/# PISTREAM-VIZ BEGIN/,/# PISTREAM-VIZ END/d' /etc/asound.conf
cat "$SRC_DIR/asound-tee.conf" >> /etc/asound.conf

echo "==> Repointing audio sources at 'pistream'"
# squeezelite: output -> pistream (Debian package uses SL_SOUNDCARD=, the
# legacy DietPi config had raw '-o <device>' arguments)
if [[ -f /etc/default/squeezelite ]]; then
  cp /etc/default/squeezelite "/etc/default/squeezelite.bak.$STAMP"
  if grep -qE '^#?SL_SOUNDCARD=' /etc/default/squeezelite; then
    sed -i -E 's|^#?SL_SOUNDCARD=.*|SL_SOUNDCARD="pistream"|' /etc/default/squeezelite
  else
    sed -i -E "s|-o [^ '\"]+|-o pistream|" /etc/default/squeezelite
  fi
fi
# shairport-sync: output_device
SP_CONF=/usr/local/etc/shairport-sync.conf
[[ -f $SP_CONF ]] || SP_CONF=/etc/shairport-sync.conf
if [[ -f $SP_CONF ]]; then
  cp "$SP_CONF" "$SP_CONF.bak.$STAMP"
  sed -i -E 's|^([[:space:]]*)output_device = ".*";|\1output_device = "pistream";|' "$SP_CONF"
fi
# bluealsa-aplay: systemd override
install -d /etc/systemd/system/bluealsa-aplay.service.d
cat > /etc/systemd/system/bluealsa-aplay.service.d/override.conf <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/bluealsa-aplay -S -d pistream
EOF

echo "==> Visualizer files and services"
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
echo "==> Done. Config backups: *.bak.$STAMP"
echo "    HDMI plugged in  -> the visualizer comes up on its own (within ~5 s)"
echo "    Login console on HDMI comes back with: systemctl stop pistream-hdmi-watch pistream-visualizer && systemctl start getty@tty1"
echo "    Test without HDMI: play some music and check 'arecord -D plughw:Loopback,1,0 -f S16_LE -d 1 /tmp/t.wav'"
