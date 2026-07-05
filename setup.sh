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
#   PISTREAM_AP_FALLBACK=0      skip the setup-AP fallback (default: 1 = install)
#   PISTREAM_REPO / PISTREAM_BRANCH   where the panel files are fetched from
#
# What it does (see README.md for the full picture):
#   1) audio output: DAC overlay via dietpi-set_hardware, or the HDMI-audio
#      workaround (config.txt + snd_bcm2835)
#   2) zram (zstd, 50%) — headroom on the 512 MB Zero 2 W
#   3) dietpi-software: Lyrion Music Server, Squeezelite, Shairport Sync, Avahi
#   4) LMS auto-config: skips the first-run wizard, installs Material Skin +
#      TIDAL local plugins, disables the analytics reporting plugin
#   5) Bluetooth: adapter on + bluez-alsa (A2DP sink)
#   6) points all players at the chosen ALSA output
#   7) control panel + bt-agent (web/install.sh)
#   8) Tailscale (install only — `tailscale up` needs interactive auth)
#   9) setup-AP fallback — captive portal when Wi-Fi is down (ap-fallback/)
#  10) optionally the HDMI visualizer (visualizer/install.sh)
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

# ---- pretty output ---------------------------------------------------------
# On a terminal: colored step headers, an animated spinner for slow commands
# (their output goes to $LOG), ✔/✖ marks. Piped/non-UTF-8 output degrades to
# plain ASCII / streamed command output automatically.
LOG=/var/log/synchrofazotron-setup.log
TTY=0;  [[ -t 1 ]] && TTY=1
UTF8=0; [[ "$(locale charmap 2>/dev/null || true)" == *UTF-8* ]] && UTF8=1
if ((TTY)); then
  BOLD=$'\e[1m' DIM=$'\e[2m' CYAN=$'\e[36m' GREEN=$'\e[32m' RED=$'\e[31m' YELLOW=$'\e[33m' RST=$'\e[0m'
else
  BOLD='' DIM='' CYAN='' GREEN='' RED='' YELLOW='' RST=''
fi
if ((UTF8)); then
  M_OK='✔' M_FAIL='✖' M_WARN='⚠' M_DOT='•' SP_FRAMES='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
else
  M_OK='+' M_FAIL='x' M_WARN='!' M_DOT='*' SP_FRAMES='|/-\'
fi
SPIN_PID=''
trap '[[ -n $SPIN_PID ]] && kill "$SPIN_PID" 2>/dev/null; ((TTY)) && printf "\e[?25h"' EXIT

step() {  # step <n/m> <title>
  printf '\n%s[%s]%s %s%s%s\n' "$CYAN" "$1" "$RST" "$BOLD" "$2" "$RST"
}
ok()   { printf '  %s%s%s %s\n' "$GREEN"  "$M_OK"   "$RST" "$1"; }
warn() { printf '  %s%s%s %s\n' "$YELLOW" "$M_WARN" "$RST" "$1"; }

run() {  # run [-w] <label> <cmd…> — spinner while it runs, output to $LOG.
         # On failure: exit with the log tail, or with -w just warn + return rc.
  local soft=0; [[ $1 == -w ]] && { soft=1; shift; }
  local label=$1 rc=0; shift
  echo "--- $(date '+%F %T') $label" >>"$LOG"
  if ((TTY)); then
    printf '\e[?25l'
    ( i=0
      while :; do
        printf '\r  %s%s%s %s\e[K' "$CYAN" "${SP_FRAMES:i++%${#SP_FRAMES}:1}" "$RST" "$label"
        sleep 0.12
      done ) & SPIN_PID=$!
    "$@" >>"$LOG" 2>&1 </dev/null || rc=$?
    kill "$SPIN_PID" 2>/dev/null || true
    wait "$SPIN_PID" 2>/dev/null || true
    SPIN_PID=''
    printf '\e[?25h'
    if ((rc == 0)); then
      printf '\r  %s%s%s %s\e[K\n' "$GREEN" "$M_OK" "$RST" "$label"
    elif ((soft)); then
      printf '\r  %s%s%s %s\e[K\n' "$YELLOW" "$M_WARN" "$RST" "$label"
      return "$rc"
    else
      printf '\r  %s%s%s %s\e[K\n' "$RED" "$M_FAIL" "$RST" "$label"
      printf '%s\n' "  ${DIM}last lines of $LOG:${RST}"
      tail -n 15 "$LOG" | sed 's/^/    /'
      exit "$rc"
    fi
  else
    printf '  %s %s ...\n' "$M_DOT" "$label"
    if ((soft)); then
      "$@" </dev/null || return $?
    else
      "$@" </dev/null
    fi
  fi
}

echo "=== $(date '+%F %T') setup.sh run ===" >>"$LOG"
((TTY)) && printf '%sdetailed log: %s%s\n' "$DIM" "$LOG" "$RST"

# Local mode only when run as a file from a repo checkout; `curl | bash` always
# fetches sub-installers from GitHub.
SRC_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo .)"
LOCAL=0
[[ "$(basename -- "$0")" == "setup.sh" && -f "$SRC_DIR/web/install.sh" ]] && LOCAL=1

REBOOT_NEEDED=0

# --------------------------------------------------------------------------
step 1/10 "Audio output: $AUDIO"
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
    ok "DAC overlay already set ($DAC_OVERLAY)"
  else
    run "DAC overlay: $DAC_OVERLAY (dietpi-set_hardware)" \
      /boot/dietpi/func/dietpi-set_hardware soundcard "$DAC_OVERLAY"
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
  ok "config.txt set up for HDMI audio (bcm2835)"
  OUT_PCM="default"
  REBOOT_NEEDED=1
else
  echo "Unknown PISTREAM_AUDIO='$AUDIO' (expected dac or hdmi)"; exit 1
fi

# --------------------------------------------------------------------------
step 2/10 "zram (zstd, 50% RAM)"
# --------------------------------------------------------------------------
if ! dpkg -s zram-tools >/dev/null 2>&1; then
  run "install zram-tools" apt-get install -y zram-tools
fi
sed -i -E 's|^#?\s*ALGO=.*|ALGO=zstd|; s|^#?\s*PERCENT=.*|PERCENT=50|' /etc/default/zramswap
systemctl restart zramswap 2>/dev/null || true
ok "zram active (zstd, 50% RAM)"

# --------------------------------------------------------------------------
step 3/10 "Players via dietpi-software (LMS, Squeezelite, Shairport, Avahi)"
# --------------------------------------------------------------------------
# DietPi software IDs: 35 = Lyrion Music Server, 36 = Squeezelite,
#                      37 = Shairport Sync,      152 = Avahi-Daemon
IDS=()
systemctl list-unit-files 2>/dev/null | grep -qE '^(lyrionmusicserver|logitechmediaserver)' || IDS+=(35)
command -v squeezelite    >/dev/null 2>&1 || IDS+=(36)
command -v shairport-sync >/dev/null 2>&1 || IDS+=(37)
command -v avahi-daemon   >/dev/null 2>&1 || IDS+=(152)
if ((${#IDS[@]})); then
  run "dietpi-software install ${IDS[*]} (takes a while on a Zero 2 W)" \
    /boot/dietpi/dietpi-software install "${IDS[@]}"
else
  ok "everything already installed"
fi

# --------------------------------------------------------------------------
step 4/10 "LMS auto-config (skip wizard, Material Skin + TIDAL, analytics off)"
# --------------------------------------------------------------------------
LMS_UNIT="$(systemctl list-unit-files --no-legend 'lyrionmusicserver.service' 'logitechmediaserver.service' 2>/dev/null | awk 'NR==1{print $1}' || true)"

lms_rpc() {  # lms_rpc '["cmd",...]' — JSON-RPC request to the local LMS
  curl -sf -m 10 -H 'Content-Type: application/json' \
    -d "{\"id\":1,\"method\":\"slim.request\",\"params\":[\"\",$1]}" \
    http://127.0.0.1:9000/jsonrpc.js
}
lms_plugin_state() {  # -> enabled|disabled|needs-install|… or "" (not installed)
  lms_rpc "[\"pref\",\"plugin.state:$1\",\"?\"]" | grep -oE '"_p2":"[^"]+"' | cut -d'"' -f4 || true
}
lms_wait() {  # the first LMS start on a Zero 2 W takes a good while
  local _
  for _ in $(seq 60); do
    lms_rpc '["serverstatus",0,0]' >/dev/null 2>&1 && return 0
    sleep 3
  done
  return 1
}
lms_install_plugins() {  # $INSTALL = "install:Name=1&…" — POST like the settings page,
                         # then wait until LMS has downloaded the zips
  local _ P PENDING
  curl -sf -m 90 -d "${INSTALL}saveSettings=1" \
    http://127.0.0.1:9000/settings/server/plugins.html >/dev/null || true
  for _ in $(seq 30); do   # state flips to needs-install once downloaded
    PENDING=0
    for P in MaterialSkin TIDAL; do
      [[ -z "$(lms_plugin_state "$P")" ]] && PENDING=1
    done
    [[ $PENDING == 0 ]] && return 0
    sleep 2
  done
  return 0
}

if run -w "waiting for LMS on :9000 (up to 3 min)" lms_wait; then
  LMS_RESTART=0
  # first-run wizard off (it only asks about language + media dirs — both can
  # be set later under Settings)
  lms_rpc '["pref","wizardDone","1"]' >/dev/null || true
  ok "first-run wizard skipped"
  # bundled "Report Analytics Data" plugin off
  if [[ "$(lms_plugin_state Analytics)" != "disabled" ]]; then
    lms_rpc '["pref","plugin.state:Analytics","disabled"]' >/dev/null || true
    LMS_RESTART=1
  fi
  ok "analytics reporting disabled"
  # Material Skin + TIDAL local: send the same POST the "Manage plugins" page
  # sends — LMS downloads the zips itself and unpacks them on its next restart
  INSTALL=""
  for P in MaterialSkin TIDAL; do
    [[ -z "$(lms_plugin_state "$P")" ]] && INSTALL+="install:$P=1&"
  done
  if [[ -n $INSTALL ]]; then
    run "plugins: Material Skin + TIDAL local" lms_install_plugins
    LMS_RESTART=1
  else
    ok "plugins already installed (Material Skin, TIDAL local)"
  fi
  if [[ $LMS_RESTART == 1 ]]; then
    if [[ -n $LMS_UNIT ]]; then
      run "restarting LMS to activate the changes" systemctl restart "$LMS_UNIT"
    else
      warn "restart LMS manually to activate the changes"
    fi
  fi
else
  warn "LMS not reachable on :9000 — skipped. Re-run setup.sh later, or configure"
  warn "by hand: http://$(hostname):9000 → Settings → Manage Plugins"
fi

# --------------------------------------------------------------------------
step 5/10 "Bluetooth (adapter + A2DP sink via bluez-alsa)"
# --------------------------------------------------------------------------
# Check for bluez itself, not the kernel module — on images without disable-bt
# the module is loaded even though bluez (bluetoothd) was never installed.
if ! dpkg -s bluez >/dev/null 2>&1 || ! systemctl cat bluetooth.service >/dev/null 2>&1; then
  run "enabling the Bluetooth adapter (dietpi-set_hardware)" \
    /boot/dietpi/func/dietpi-set_hardware bluetooth enable
  REBOOT_NEEDED=1
else
  ok "adapter already enabled (bluez installed)"
fi
if ! dpkg -s bluez-alsa-utils >/dev/null 2>&1; then
  run "install bluez-alsa-utils" apt-get install -y bluez-alsa-utils
fi
systemctl enable --now bluealsa.service bluealsa-aplay.service 2>/dev/null || true
ok "A2DP sink enabled (bluez-alsa)"

# --------------------------------------------------------------------------
step 6/10 "Pointing players at the audio output ($OUT_PCM)"
# --------------------------------------------------------------------------
# If the visualizer is installed, players go through its 'pistream' tee device
# instead — do not touch those. (visualizer/install.sh manages them.)
# squeezelite
SL=/etc/default/squeezelite
if [[ -f $SL ]]; then
  SL_CHANGED=0
  if grep -q -- '-o pistream' "$SL"; then
    ok "squeezelite: already routed through the visualizer tee, leaving as is"
  elif grep -qE -- '-o +[^ ]+' "$SL"; then
    sed -i -E "s|-o [^ ']+|-o $OUT_PCM|" "$SL"
    SL_CHANGED=1
  else
    warn "no '-o <device>' found in $SL —"
    warn "set the output to '$OUT_PCM' manually (dietpi-config or the file itself)"
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
    ok "squeezelite → $OUT_PCM"
  fi
fi
# shairport-sync
SP_CONF=/usr/local/etc/shairport-sync.conf
[[ -f $SP_CONF ]] || SP_CONF=/etc/shairport-sync.conf
if [[ -f $SP_CONF ]]; then
  if grep -q 'output_device = "pistream"' "$SP_CONF"; then
    ok "shairport-sync: already routed through the visualizer tee, leaving as is"
  else
    sed -i -E "s|^([[:space:]]*)(//[[:space:]]*)?output_device = \".*\";|\1output_device = \"$OUT_PCM\";|" "$SP_CONF"
    systemctl restart shairport-sync 2>/dev/null || true
    ok "shairport-sync → $OUT_PCM"
  fi
fi
# bluealsa-aplay (systemd override — the unit has no config file)
BA_OVR=/etc/systemd/system/bluealsa-aplay.service.d/override.conf
if [[ -f $BA_OVR ]] && grep -q pistream "$BA_OVR"; then
  ok "bluealsa-aplay: already routed through the visualizer tee, leaving as is"
else
  install -d "$(dirname "$BA_OVR")"
  cat > "$BA_OVR" <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/bluealsa-aplay -S -d $OUT_PCM
EOF
  systemctl daemon-reload
  systemctl restart bluealsa-aplay 2>/dev/null || true
  ok "bluealsa-aplay → $OUT_PCM"
fi

# --------------------------------------------------------------------------
step 7/10 "Control panel + bt-agent"
# --------------------------------------------------------------------------
if [[ $LOCAL == 1 ]]; then
  run "web/install.sh (panel on :8787 + bt-agent)" bash "$SRC_DIR/web/install.sh"
else
  run "web/install.sh (panel on :8787 + bt-agent)" \
    bash -c "set -euo pipefail; curl -fsSL '$RAW/web/install.sh' | bash"
fi

# --------------------------------------------------------------------------
step 8/10 "Tailscale"
# --------------------------------------------------------------------------
ts_install() {  # to a file first — `| sh </dev/null` starves sh of the script
  local f rc=0
  f="$(mktemp)"
  curl -fsSL https://tailscale.com/install.sh -o "$f" && sh "$f" || rc=$?
  rm -f "$f"
  return "$rc"
}
if [[ "${PISTREAM_TAILSCALE:-1}" == "1" ]]; then
  if command -v tailscale >/dev/null 2>&1; then
    ok "already installed"
  else
    run "install Tailscale (tailscale.com/install.sh)" ts_install
  fi
else
  ok "skipped (PISTREAM_TAILSCALE=0)"
fi

# --------------------------------------------------------------------------
step 9/10 "Setup-AP fallback (captive portal when Wi-Fi is down)"
# --------------------------------------------------------------------------
if [[ "${PISTREAM_AP_FALLBACK:-1}" == "1" ]]; then
  if [[ $LOCAL == 1 ]]; then
    run "ap-fallback/install.sh" bash "$SRC_DIR/ap-fallback/install.sh"
  else
    run "ap-fallback/install.sh" \
      bash -c "set -euo pipefail; curl -fsSL '$RAW/ap-fallback/install.sh' | bash"
  fi
else
  ok "skipped (PISTREAM_AP_FALLBACK=0)"
fi

# --------------------------------------------------------------------------
step 10/10 "HDMI visualizer"
# --------------------------------------------------------------------------
if [[ "${PISTREAM_VISUALIZER:-0}" == "1" ]]; then
  if [[ $LOCAL == 1 ]]; then
    run "visualizer/install.sh" bash "$SRC_DIR/visualizer/install.sh"
  else
    run "visualizer/install.sh" \
      bash -c "set -euo pipefail; curl -fsSL '$RAW/visualizer/install.sh' | bash"
  fi
else
  ok "skipped (set PISTREAM_VISUALIZER=1 to install; can be run any time later)"
fi

# --------------------------------------------------------------------------
echo
printf '%s%s%s %sDone.%s Remaining MANUAL steps:\n' "$GREEN" "$M_OK" "$RST" "$BOLD" "$RST"
echo
echo "  1) Tailscale:    tailscale up     (authorize via the printed URL;"
echo "                   then disable key expiry for this machine in the admin panel)"
echo "  2) LMS TIDAL:    http://$(hostname):9000 → Settings → Advanced → TIDAL:"
echo "                   authorize your TIDAL account (Material Skin + TIDAL local are"
echo "                   installed automatically; optional plugin: Radio Browser)"
echo "  3) Panel:        http://$(hostname):8787 (language switch is in /settings)"
if [[ $REBOOT_NEEDED == 1 ]]; then
  echo
  printf '  %s%s REBOOT REQUIRED%s (audio overlay / bluetooth changes):  reboot\n' "$YELLOW" "$M_WARN" "$RST"
  echo "    After the reboot check:  aplay -l   (the expected sound card is listed)"
fi
