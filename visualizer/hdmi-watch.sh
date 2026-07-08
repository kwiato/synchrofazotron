#!/bin/bash
# Fireworks for special occasions: watches the HDMI status and starts/stops
# the visualizer. Hotplug status is read from DRM (/sys/class/drm/*-HDMI-*/status).
set -u

VIZ=pistream-visualizer.service
INTERVAL=5
# Manual off-switch written by the panel toggle. When present the visualizer
# stays off regardless of HDMI — the user's intent wins over the hotplug logic.
DISABLED_FLAG=/opt/pistream-visualizer/disabled

hdmi_connected() {
    local f
    for f in /sys/class/drm/card*-HDMI-A-*/status; do
        [[ -r $f ]] || continue
        [[ $(<"$f") == connected ]] && return 0
    done
    return 1
}

ensure_off() { systemctl is-active -q "$VIZ" && systemctl stop "$VIZ"; return 0; }
ensure_on()  { systemctl is-active -q "$VIZ" || systemctl start "$VIZ"; return 0; }

# Without KMS there is no DRM status, so hotplug cannot be detected. Fallback:
# the visualizer runs whenever enabled (the Pi is managed over SSH anyway; cava
# with no monitor attached is only a few % CPU). Still poll so the panel toggle
# takes effect.
if ! compgen -G "/sys/class/drm/card*-HDMI-A-*/status" >/dev/null; then
    echo "No /sys/class/drm/*-HDMI-*/status (kernel without KMS?) — visualizer runs whenever enabled."
    while :; do
        if [[ -e $DISABLED_FLAG ]]; then ensure_off; else ensure_on; fi
        sleep "$INTERVAL"
    done
fi

while :; do
    if [[ -e $DISABLED_FLAG ]]; then
        ensure_off
    elif hdmi_connected; then
        ensure_on
    else
        ensure_off
    fi
    sleep "$INTERVAL"
done
