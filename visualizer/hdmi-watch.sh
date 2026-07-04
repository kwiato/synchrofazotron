#!/bin/bash
# Fireworks for special occasions: watches the HDMI status and starts/stops
# the visualizer. Hotplug status is read from DRM (/sys/class/drm/*-HDMI-*/status).
set -u

VIZ=pistream-visualizer.service
INTERVAL=5

hdmi_connected() {
    local f
    for f in /sys/class/drm/card*-HDMI-A-*/status; do
        [[ -r $f ]] || continue
        [[ $(<"$f") == connected ]] && return 0
    done
    return 1
}

# Without KMS there is no DRM status, so hotplug cannot be detected. Fallback:
# the visualizer runs PERMANENTLY (the Pi is managed over SSH anyway; cava with
# no monitor attached is only a few % CPU). sleep infinity so Restart=always
# does not respawn the unit in a loop.
if ! compgen -G "/sys/class/drm/card*-HDMI-A-*/status" >/dev/null; then
    echo "No /sys/class/drm/*-HDMI-*/status (kernel without KMS?) — visualizer stays on permanently."
    systemctl start "$VIZ"
    exec sleep infinity
fi

while :; do
    if hdmi_connected; then
        systemctl is-active -q "$VIZ" || systemctl start "$VIZ"
    else
        if systemctl is-active -q "$VIZ"; then
            systemctl stop "$VIZ"
        fi
    fi
    sleep "$INTERVAL"
done
