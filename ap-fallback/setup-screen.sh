#!/bin/bash
# Paints the HDMI console (tty1) with setup instructions + a Wi-Fi QR code
# while the fallback AP is up. Called by net-watch.sh:
#
#   setup-screen.sh show   -> stop the visualizer, draw the instructions
#   setup-screen.sh clear  -> blank the console (hdmi-watch restarts the viz)
#
# hdmi-watch.sh keeps the visualizer off while /run/pistream-ap.active exists,
# so nothing repaints tty1 underneath us. Text is diacritic-free on purpose:
# the console font is not guaranteed to carry Polish glyphs.
set -u

TTY=/dev/tty1
DIR=/opt/pistream-ap
AP_IP=192.168.4.1

conf() { grep -oP "^$1=\K.*" "$DIR/hostapd.conf" 2>/dev/null | head -n1; }

# WIFI: payload — backslash-escape the chars the format reserves (\ ; , : ")
qr_escape() { sed 's/[\\;,:"]/\\&/g' <<<"$1"; }

show() {
    # The visualizer owns tty1 — release it first.
    systemctl stop pistream-visualizer.service 2>/dev/null || true

    local ssid pass qr=""
    ssid=$(conf ssid)
    pass=$(conf wpa_passphrase)
    if command -v qrencode >/dev/null; then
        qr=$(qrencode -t ANSI -m 2 \
            "WIFI:T:WPA;S:$(qr_escape "$ssid");P:$(qr_escape "$pass");;" \
            2>/dev/null | sed 's/^/      /')
    fi

    {
        # clear, home, hide cursor
        printf '\033[2J\033[H\033[?25l\n'
        printf '   SYNCHROFAZOTRON - KONFIGURACJA WI-FI / WI-FI SETUP\n'
        printf '   ==================================================\n\n'
        printf '   Nie znalazlem znanej sieci Wi-Fi, wiec nadaje wlasna.\n'
        printf '   No known Wi-Fi found - the device broadcasts its own network.\n\n'
        printf '      siec / network:    %s\n' "$ssid"
        printf '      haslo / password:  %s\n\n' "$pass"
        if [[ -n $qr ]]; then
            printf '%s\n\n' "$qr"
            printf '   Zeskanuj aparatem telefonu, aby dolaczyc do tej sieci.\n'
            printf '   Scan with your phone camera to join this network.\n\n'
        fi
        printf '   Po polaczeniu strona konfiguracji otworzy sie sama\n'
        printf '   (albo wejdz na http://%s).\n' "$AP_IP"
        printf '   After joining, the setup page opens on its own\n'
        printf '   (or go to http://%s).\n' "$AP_IP"
    } > "$TTY" 2>/dev/null || true
}

clear_screen() {
    printf '\033[2J\033[H\033[?25h' > "$TTY" 2>/dev/null || true
}

case "${1:-}" in
    show)  show ;;
    clear) clear_screen ;;
    *)     echo "usage: $0 show|clear" >&2; exit 2 ;;
esac
