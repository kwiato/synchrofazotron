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
#   PISTREAM_VISUALIZER=1|0     also install the HDMI audio visualizer
#                               (default: ask on a terminal; 0 when piped)
#   PISTREAM_TAILSCALE=0        skip Tailscale install (default: 1 = install)
#   PISTREAM_AP_FALLBACK=0      skip the setup-AP fallback (default: 1 = install)
#   PISTREAM_REPO / PISTREAM_BRANCH   where the panel files are fetched from
#
# What it does (see README.md for the full picture):
#   1) audio output: DAC overlay + I2C (for i2cdetect diagnostics) via
#      dietpi-set_hardware, or the HDMI-audio workaround (config.txt + snd_bcm2835)
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
# (their output goes to $LOG), ✔/✖ marks. While a step runs, SPACE toggles a
# live view of the log on the terminal's alternate screen (press again to go
# back to the summary). Piped/non-UTF-8 output degrades to plain ASCII /
# streamed command output automatically.
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
# Key input for the live-log toggle: read the controlling terminal directly —
# under `curl | bash` stdin is the pipe, but /dev/tty still points at the user.
KEY_IN=0
((TTY)) && { : </dev/tty; } 2>/dev/null && KEY_IN=1
STTY_SAVED=''
((KEY_IN)) && { STTY_SAVED="$(stty -g </dev/tty 2>/dev/null || true)"; stty -echo </dev/tty 2>/dev/null || true; }

VERBOSE=0; TAIL_PID=''; CMD_PID=''; FETCH_DIR=''
trap '[[ -n $TAIL_PID ]] && kill "$TAIL_PID" 2>/dev/null || true
      [[ -n $STTY_SAVED ]] && stty "$STTY_SAVED" </dev/tty 2>/dev/null || true
      [[ -n $FETCH_DIR ]] && rm -rf "$FETCH_DIR" || true
      ((TTY)) && printf "\e[?1049l\e[?25h" || true' EXIT

log_show() {  # live-log view: switch to the terminal alternate screen + tail -f
  printf '\e[?1049h\e[H\e[2J'
  printf '%s--- live log (%s) --- space = back to the summary ---%s\n' "$DIM" "$LOG" "$RST"
  tail -n 25 -f "$LOG" 2>/dev/null & TAIL_PID=$!
  VERBOSE=1
}
log_hide() {  # stop the tail and return to the untouched main screen
  [[ -n $TAIL_PID ]] && { kill "$TAIL_PID" 2>/dev/null || true; wait "$TAIL_PID" 2>/dev/null || true; }
  TAIL_PID=''
  printf '\e[?1049l'
  VERBOSE=0
}

ask_yn() {  # ask_yn <question> — one key from /dev/tty; y/t = yes, anything
            # else (or 60 s of silence, so unattended runs move on) = no
  local key=''
  printf '%s?%s %s [y/N] ' "$YELLOW" "$RST" "$1"
  IFS= read -rsn1 -t 60 key </dev/tty 2>/dev/null || key=''
  if [[ $key == [yYtT] ]]; then printf 'yes\n'; return 0; fi
  printf 'no\n'; return 1
}

step() {  # step <n/m> <title>
  printf '\n%s[%s]%s %s%s%s\n' "$CYAN" "$1" "$RST" "$BOLD" "$2" "$RST"
}
ok()   { printf '  %s%s%s %s\n' "$GREEN"  "$M_OK"   "$RST" "$1"; }
warn() { printf '  %s%s%s %s\n' "$YELLOW" "$M_WARN" "$RST" "$1"; }

run() {  # run [-w] <label> <cmd…> — spinner while it runs, output to $LOG.
         # While a command runs, SPACE toggles a live view of $LOG (alt screen).
         # On failure: exit with the log tail, or with -w just warn + return rc.
  local soft=0; [[ $1 == -w ]] && { soft=1; shift; }
  local label=$1 rc=0; shift
  echo "--- $(date '+%F %T') $label" >>"$LOG"
  if ((TTY)); then
    local i=0 key hint=''
    ((KEY_IN)) && hint=" ${DIM}[space: log]${RST}"
    printf '\e[?25l'
    "$@" >>"$LOG" 2>&1 </dev/null & CMD_PID=$!
    while kill -0 "$CMD_PID" 2>/dev/null; do
      ((VERBOSE)) || printf '\r  %s%s%s %s%s\e[K' "$CYAN" "${SP_FRAMES:i++%${#SP_FRAMES}:1}" "$RST" "$label" "$hint"
      key=''
      if ((KEY_IN)); then
        IFS= read -rsn1 -t 0.12 key </dev/tty 2>/dev/null || true
      else
        sleep 0.12
      fi
      if [[ $key == ' ' ]]; then
        if ((VERBOSE)); then log_hide; else log_show; fi
      fi
    done
    wait "$CMD_PID" || rc=$?
    CMD_PID=''
    ((VERBOSE)) && log_hide
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
((KEY_IN)) && printf '%swhile a step runs: space = show/hide the live log%s\n' "$DIM" "$RST"

# Local mode only when run as a file from a repo checkout; `curl | bash`
# downloads the repo once as a tarball (below) and continues locally.
SRC_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo .)"
LOCAL=0
[[ "$(basename -- "$0")" == "setup.sh" && -f "$SRC_DIR/web/install.sh" ]] && LOCAL=1

fetch_repo() {  # whole repo in one request — the burst of per-file fetches
                # from raw.githubusercontent.com was getting HTTP 429
  curl -fsSL --retry 5 --retry-delay 2 \
    "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH" \
    | tar -xz -C "$FETCH_DIR" --strip-components=1
}
if ((!LOCAL)); then
  FETCH_DIR="$(mktemp -d)"
  if run -w "downloading $REPO@$BRANCH (single tarball)" fetch_repo; then
    SRC_DIR="$FETCH_DIR"
    LOCAL=1
  else
    warn "tarball download failed — falling back to per-file fetches"
  fi
fi

REBOOT_NEEDED=0

# Visualizer: env var wins; otherwise ask up front (so the answer is given
# before the long installs start), defaulting to "no" without a keyboard.
# An already-installed visualizer is just updated, no question asked.
VIZ="${PISTREAM_VISUALIZER:-}"
if [[ -z $VIZ ]]; then
  if [[ -f /opt/pistream-visualizer/cava.conf ]]; then
    VIZ=1
  elif ((KEY_IN)) && { echo; ask_yn "install the HDMI visualizer (music bars on a monitor)?"; }; then
    VIZ=1
  else
    VIZ=0
  fi
fi

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
  # I2C on — the PCM5122 sits on the I2C bus; userspace access (/dev/i2c-1 +
  # i2c-tools) is what makes the `i2cdetect -y 1` check from dac-setup.md work
  if grep -qE '^dtparam=i2c_arm=on' "$CFG" && command -v i2cdetect >/dev/null 2>&1; then
    ok "I2C already enabled"
  else
    run "enabling I2C (dietpi-set_hardware)" \
      /boot/dietpi/func/dietpi-set_hardware i2c enable
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
  # -C 5: close the ALSA device 5 s after pause/stop. Without it a paused
  # squeezelite holds the DAC forever and blocks Bluetooth/AirPlay (a hardware
  # DAC has a single substream — unlike HDMI audio, sources cannot mix there).
  if grep -qE -- '-o pistream|^SL_SOUNDCARD="?pistream' "$SL"; then
    ok "squeezelite: already routed through the visualizer tee, leaving as is"
  elif grep -qE "^ARGS=" "$SL"; then
    # DietPi config: a single ARGS='…' line with raw squeezelite arguments
    # (by default it has no -o at all — append one inside the quotes)
    if ! grep -qF -- "-o $OUT_PCM" "$SL" || ! grep -qE -- '-C ?[0-9]+' "$SL"; then
      if grep -qE -- '^ARGS=.*-o ' "$SL"; then
        sed -i -E "s|-o [^ '\"]+|-o $OUT_PCM|" "$SL"
      else
        sed -i -E "s|^ARGS=(['\"])(.*)\1|ARGS=\1\2 -o $OUT_PCM\1|" "$SL"
      fi
      grep -qE -- '-C ?[0-9]+' "$SL" || sed -i -E "s|-o |-C 5 -o |" "$SL"
      SL_CHANGED=1
    fi
  elif grep -qE '^#?SL_SOUNDCARD=' "$SL"; then
    # Debian-package config: variables sourced by the init script
    # (SL_SOUNDCARD becomes -o, SB_EXTRA_ARGS is appended)
    if ! grep -qE "^SL_SOUNDCARD=\"$OUT_PCM\"\$" "$SL"; then
      sed -i -E "s|^#?SL_SOUNDCARD=.*|SL_SOUNDCARD=\"$OUT_PCM\"|" "$SL"
      SL_CHANGED=1
    fi
    if ! { grep -E '^SB_EXTRA_ARGS=' "$SL" | grep -qE -- '-C ?[0-9]+'; }; then
      if grep -qE '^SB_EXTRA_ARGS="' "$SL"; then
        sed -i -E 's|^SB_EXTRA_ARGS="|SB_EXTRA_ARGS="-C 5 |' "$SL"
      elif grep -qE '^#?SB_EXTRA_ARGS=' "$SL"; then
        sed -i -E '0,/^#?SB_EXTRA_ARGS=/s|^#?SB_EXTRA_ARGS=.*|SB_EXTRA_ARGS="-C 5"|' "$SL"
      else
        echo 'SB_EXTRA_ARGS="-C 5"' >> "$SL"
      fi
      SL_CHANGED=1
    fi
  elif grep -qE -- '-o +[^ ]+' "$SL"; then
    # legacy DietPi config: raw squeezelite arguments
    if ! grep -qF -- "-o $OUT_PCM" "$SL" || ! grep -qE -- '-C ?[0-9]+' "$SL"; then
      sed -i -E "s|-o [^ '\"]+|-o $OUT_PCM|" "$SL"
      grep -qE -- '-C ?[0-9]+' "$SL" || sed -i -E "s|-o |-C 5 -o |" "$SL"
      SL_CHANGED=1
    fi
  else
    warn "unrecognized format of $SL —"
    warn "set the output to '$OUT_PCM' manually (dietpi-config or the file itself)"
  fi
  if [[ $SL_CHANGED == 1 ]]; then
    systemctl restart squeezelite 2>/dev/null || true
    ok "squeezelite → $OUT_PCM (with -C 5)"
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
# bluealsa-aplay (systemd override — the unit has no config file).
# NOTE: the device option must be the long --pcm= form: bluez-alsa 3.x used
# -d, 4.x renamed it, and a stale -d makes the service crash-loop silently.
BA_OVR=/etc/systemd/system/bluealsa-aplay.service.d/override.conf
if [[ -f $BA_OVR ]] && grep -q pistream "$BA_OVR"; then
  if grep -qE -- '-d +pistream' "$BA_OVR"; then
    sed -i -E 's|-d +pistream|--pcm=pistream|' "$BA_OVR"
    systemctl daemon-reload
    systemctl reset-failed bluealsa-aplay 2>/dev/null || true
    systemctl restart bluealsa-aplay 2>/dev/null || true
    ok "bluealsa-aplay: fixed the stale -d option (bluez-alsa 4.x), still routed via the tee"
  else
    ok "bluealsa-aplay: already routed through the visualizer tee, leaving as is"
  fi
else
  install -d "$(dirname "$BA_OVR")"
  cat > "$BA_OVR" <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/bluealsa-aplay -S --pcm=$OUT_PCM
EOF
  systemctl daemon-reload
  systemctl reset-failed bluealsa-aplay 2>/dev/null || true
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
    bash -c "set -euo pipefail; curl -fsSL --retry 5 --retry-delay 2 '$RAW/web/install.sh' | bash"
fi

# --------------------------------------------------------------------------
step 8/10 "Tailscale"
# --------------------------------------------------------------------------
ts_install() {  # to a file first — `| sh </dev/null` starves sh of the script
  local f rc=0
  f="$(mktemp)"
  curl -fsSL --retry 5 --retry-delay 2 https://tailscale.com/install.sh -o "$f" && sh "$f" || rc=$?
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
      bash -c "set -euo pipefail; curl -fsSL --retry 5 --retry-delay 2 '$RAW/ap-fallback/install.sh' | bash"
  fi
else
  ok "skipped (PISTREAM_AP_FALLBACK=0)"
fi

# --------------------------------------------------------------------------
step 10/10 "HDMI visualizer"
# --------------------------------------------------------------------------
if [[ "$VIZ" == "1" ]]; then
  if [[ $LOCAL == 1 ]]; then
    run "visualizer/install.sh" bash "$SRC_DIR/visualizer/install.sh"
  else
    run "visualizer/install.sh" \
      bash -c "set -euo pipefail; curl -fsSL --retry 5 --retry-delay 2 '$RAW/visualizer/install.sh' | bash"
  fi
else
  ok "skipped (re-run setup.sh or use PISTREAM_VISUALIZER=1 to install it any time)"
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
