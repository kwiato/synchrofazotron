#!/bin/bash
# Fajerwerki na specjalną okazję: pilnuje statusu HDMI i włącza/wyłącza
# wizualizer. Status hotplug czytamy z DRM (/sys/class/drm/*-HDMI-*/status).
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

# Bez KMS nie ma statusu DRM, więc nie wykryjemy hotplugu. Fallback:
# wizualizer działa NA STAŁE (obsługa Pi i tak przez SSH; cava bez wpiętego
# monitora to tylko kilka % CPU). sleep infinity, żeby Restart=always nie
# respawnował usługi w kółko.
if ! compgen -G "/sys/class/drm/card*-HDMI-A-*/status" >/dev/null; then
    echo "Brak /sys/class/drm/*-HDMI-*/status (kernel bez KMS?) — wizualizer na stałe."
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
