#!/bin/bash
# Synchrofazotron full setup — turns a clean DietPi install into a Synchrofazotron audio player.
#
#   curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/setup.sh | sudo bash
#
# Idempotent: safe to re-run on an already configured device (it skips what is
# already in place). Configuration via environment variables:
#
#   PISTREAM_AUDIO=dac|hdmi     audio output (default: dac = InnoMaker/BossDAC HAT)
#   PISTREAM_DAC_OVERLAY=...    DAC device-tree overlay
#                               (default: allo-boss-dac-pcm512x-audio; the other
#                               candidate for the PCM5122 is hifiberry-dacplus)
#   PISTREAM_VISUALIZER=1       also install the HDMI audio visualizer (default: 0)
#   PISTREAM_TAILSCALE=0        skip Tailscale install (default: 1 = install)
#   PISTREAM_REPO / PISTREAM_BRANCH   where the panel files are fetched from
#
# What it does (see README.md for the full picture):
#   1) audio output: DAC overlay via dietpi-set_hardware, or the HDMI-audio
#      workaround (config.txt + snd_bcm2835)
#   2) zram (zstd, 50%) — headroom on the 512 MB Zero 2 W
#   3) dietpi-software: Lyrion Music Server, Squeezelite, Shairport Sync, Avahi
#   4) Bluetooth: adapter on + bluez-alsa (A2DP sink)
#   5) points all players at the chosen ALSA output
#   6) control panel + bt-agent (web/install.sh)
#   7) Tailscale (install only — `tailscale up` needs interactive auth)
#   8) optionally the HDMI visualizer (visualizer/install.sh)
#
# Manual steps that cannot be automated are printed at the end.
set -euo pipefail

REPO="${PISTREAM_REPO:-kwiato/synchrofazotron}"
BRANCH="${PISTREAM_BRANCH:-main}"
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH"
AUDIO="${PISTREAM_AUDIO:-dac}"
DAC_OVERLAY="${PISTREAM_DAC_OVERLAY:-allo-boss-dac-pcm512x-audio}"

[[ $EUID -eq 0 ]] || { echo "Run as root: sudo bash setup.sh"; exit 1; }
[[ -d /boot/dietpi ]] || { echo "This script targets DietPi (missing /boot/dietpi)."; exit 1; }
export DEBIAN_FRONTEND=noninteractive
export G_INTERACTIVE=0   # tell DietPi scripts to never prompt

# Local mode only when run as a file from a repo checkout; `curl | bash` always
# fetches sub-installers from GitHub.
SRC_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo .)"
LOCAL=0
[[ "$(basename -- "$0")" == "setup.sh" && -f "$SRC_DIR/web/install.sh" ]] && LOCAL=1

REBOOT_NEEDED=0

# --------------------------------------------------------------------------
echo "==> [1/8] Audio output: $AUDIO"
# --------------------------------------------------------------------------
CFG=/boot/firmware/config.txt
[[ -f $CFG ]] || CFG=/boot/config.txt

set_cfg() {  # set_cfg <key> <value> — replace (even commented-out) or append
  local key=$1 val=$2
  if grep -qE "^#?${key}=" "$CFG"; then
    sed -i -E "s|^#?${key}=.*|${key}=${val}|" "$CFG"
  else
    echo "${key}=${val}" >> "$CFG"
  fi
}

if [[ $AUDIO == dac ]]; then
  if grep -qE "^dtoverlay=${DAC_OVERLAY}\b" "$CFG"; then
    echo "    DAC overlay already set ($DAC_OVERLAY)"
  else
    /boot/dietpi/func/dietpi-set_hardware soundcard "$DAC_OVERLAY" </dev/null
    REBOOT_NEEDED=1
  fi
  OUT_PCM="hw:CARD=BossDAC,DEV=0"
elif [[ $AUDIO == hdmi ]]; then
  # HDMI-audio workaround (documented in dac-setup.md): on-board bcm2835 audio
  # over the HDMI cable — used while the DAC HAT is dead/absent.
  set_cfg "dtparam=audio" on
  set_cfg "hdmi_drive" 2            # 2 = HDMI mode with audio (1 = DVI, no audio)
  set_cfg "hdmi_force_hotplug" 1    # keep HDMI alive even with no display attached
  set_cfg "hdmi_blanking" 0         # never power the display down
  # disable any DAC overlay left over from a previous config
  sed -i -E 's|^(dtoverlay=(hifiberry|allo-boss)[^#]*)|#\1|' "$CFG"
  # DietPi blacklists the on-board audio module — undo that and load it at boot
  if [[ -f /etc/modprobe.d/dietpi-disable_rpi_audio.conf ]]; then
    sed -i 's|^blacklist snd_bcm2835|#blacklist snd_bcm2835|' /etc/modprobe.d/dietpi-disable_rpi_audio.conf
  fi
  echo snd_bcm2835 > /etc/modules-load.d/hdmi-audio.conf
  # default ALSA device = card 0 (bcm2835 HDMI once the DAC overlay is off)
  if [[ ! -f /etc/asound.conf ]] || ! grep -q 'pcm.!default' /etc/asound.conf; then
    cat >> /etc/asound.conf <<'EOF'
pcm.!default { type hw; card 0; }
ctl.!default { type hw; card 0; }
EOF
  fi
  OUT_PCM="default"
  REBOOT_NEEDED=1
else
  echo "Unknown PISTREAM_AUDIO='$AUDIO' (expected dac or hdmi)"; exit 1
fi

# --------------------------------------------------------------------------
echo "==> [2/8] zram (zstd, 50% RAM)"
# --------------------------------------------------------------------------
if ! dpkg -s zram-tools >/dev/null 2>&1; then
  apt-get install -y zram-tools </dev/null
fi
sed -i -E 's|^#?\s*ALGO=.*|ALGO=zstd|; s|^#?\s*PERCENT=.*|PERCENT=50|' /etc/default/zramswap
systemctl restart zramswap 2>/dev/null || true

# --------------------------------------------------------------------------
echo "==> [3/8] Players via dietpi-software (LMS, Squeezelite, Shairport, Avahi)"
# --------------------------------------------------------------------------
# DietPi software IDs: 35 = Lyrion Music Server, 36 = Squeezelite,
#                      37 = Shairport Sync,      152 = Avahi-Daemon
IDS=()
systemctl list-unit-files 2>/dev/null | grep -qE '^(lyrionmusicserver|logitechmediaserver)' || IDS+=(35)
command -v squeezelite    >/dev/null 2>&1 || IDS+=(36)
command -v shairport-sync >/dev/null 2>&1 || IDS+=(37)
command -v avahi-daemon   >/dev/null 2>&1 || IDS+=(152)
if ((${#IDS[@]})); then
  echo "    installing: ${IDS[*]} (this takes a while on a Zero 2 W)"
  /boot/dietpi/dietpi-software install "${IDS[@]}" </dev/null
else
  echo "    everything already installed"
fi

# --------------------------------------------------------------------------
echo "==> [4/8] Bluetooth (adapter + A2DP sink via bluez-alsa)"
# --------------------------------------------------------------------------
if ! lsmod | grep -q '^bluetooth' && ! systemctl is-active -q bluetooth; then
  /boot/dietpi/func/dietpi-set_hardware bluetooth enable </dev/null
  REBOOT_NEEDED=1
fi
if ! dpkg -s bluez-alsa-utils >/dev/null 2>&1; then
  apt-get install -y bluez-alsa-utils </dev/null
fi
systemctl enable --now bluealsa.service bluealsa-aplay.service 2>/dev/null || true

# --------------------------------------------------------------------------
echo "==> [5/8] Pointing players at the audio output ($OUT_PCM)"
# --------------------------------------------------------------------------
# If the visualizer is installed, players go through its 'pistream' tee device
# instead — do not touch those. (visualizer/install.sh manages them.)
# squeezelite
SL=/etc/default/squeezelite
if [[ -f $SL ]]; then
  SL_CHANGED=0
  if grep -q -- '-o pistream' "$SL"; then
    echo "    squeezelite: already routed through the visualizer tee, leaving the output as is"
  elif grep -qE -- '-o +[^ ]+' "$SL"; then
    sed -i -E "s|-o [^ ']+|-o $OUT_PCM|" "$SL"
    SL_CHANGED=1
  else
    echo "    WARNING: no '-o <device>' found in $SL —"
    echo "             set the output to '$OUT_PCM' manually (dietpi-config or the file itself)"
  fi
  # -C 5: close the ALSA device 5 s after pause/stop. Without it a paused
  # squeezelite holds the DAC forever and blocks Bluetooth/AirPlay (a hardware
  # DAC has a single substream — unlike HDMI audio, sources cannot mix there).
  if grep -qE -- '-o ' "$SL" && ! grep -qE -- '-C ?[0-9]+' "$SL"; then
    sed -i -E "s|-o |-C 5 -o |" "$SL"
    SL_CHANGED=1
  fi
  if [[ $SL_CHANGED == 1 ]]; then
    systemctl restart squeezelite 2>/dev/null || true
  fi
fi
# shairport-sync
SP_CONF=/usr/local/etc/shairport-sync.conf
[[ -f $SP_CONF ]] || SP_CONF=/etc/shairport-sync.conf
if [[ -f $SP_CONF ]]; then
  if grep -q 'output_device = "pistream"' "$SP_CONF"; then
    echo "    shairport-sync: already routed through the visualizer tee, leaving as is"
  else
    sed -i -E "s|^([[:space:]]*)(//[[:space:]]*)?output_device = \".*\";|\1output_device = \"$OUT_PCM\";|" "$SP_CONF"
    systemctl restart shairport-sync 2>/dev/null || true
  fi
fi
# bluealsa-aplay (systemd override — the unit has no config file)
BA_OVR=/etc/systemd/system/bluealsa-aplay.service.d/override.conf
if [[ -f $BA_OVR ]] && grep -q pistream "$BA_OVR"; then
  echo "    bluealsa-aplay: already routed through the visualizer tee, leaving as is"
else
  install -d "$(dirname "$BA_OVR")"
  cat > "$BA_OVR" <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/bluealsa-aplay -S -d $OUT_PCM
EOF
  systemctl daemon-reload
  systemctl restart bluealsa-aplay 2>/dev/null || true
fi

# --------------------------------------------------------------------------
echo "==> [6/8] Control panel + bt-agent"
# --------------------------------------------------------------------------
if [[ $LOCAL == 1 ]]; then
  bash "$SRC_DIR/web/install.sh"
else
  curl -fsSL "$RAW/web/install.sh" | bash
fi

# --------------------------------------------------------------------------
echo "==> [7/8] Tailscale"
# --------------------------------------------------------------------------
if [[ "${PISTREAM_TAILSCALE:-1}" == "1" ]]; then
  if command -v tailscale >/dev/null 2>&1; then
    echo "    already installed"
  else
    curl -fsSL https://tailscale.com/install.sh | sh </dev/null
  fi
else
  echo "    skipped (PISTREAM_TAILSCALE=0)"
fi

# --------------------------------------------------------------------------
echo "==> [8/8] HDMI visualizer"
# --------------------------------------------------------------------------
if [[ "${PISTREAM_VISUALIZER:-0}" == "1" ]]; then
  if [[ $LOCAL == 1 ]]; then
    bash "$SRC_DIR/visualizer/install.sh"
  else
    curl -fsSL "$RAW/visualizer/install.sh" | bash
  fi
else
  echo "    skipped (set PISTREAM_VISUALIZER=1 to install; can be run any time later)"
fi

# --------------------------------------------------------------------------
echo
echo "==> Done. Remaining MANUAL steps:"
echo
echo "  1) Tailscale:    tailscale up     (authorize via the printed URL;"
echo "                   then disable key expiry for this machine in the admin panel)"
echo "  2) LMS plugins:  http://$(hostname):9000 → Settings → Manage Plugins:"
echo "                   enable 'TIDAL local' (disable old 'TIDAL'), 'Material Skin',"
echo "                   optionally 'Radio Browser'; restart LMS, then authorize TIDAL"
echo "  3) Panel:        http://$(hostname):8787 (language switch is in /settings)"
if [[ $REBOOT_NEEDED == 1 ]]; then
  echo
  echo "  ⚠ REBOOT REQUIRED (audio overlay / bluetooth changes):  reboot"
  echo "    After the reboot check:  aplay -l   (the expected sound card is listed)"
fi
