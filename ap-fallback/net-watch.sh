#!/bin/bash
# Synchrofazotron net-watch — fallback setup AP ("Chromecast mode").
#
# Runs permanently. When the device has had no Wi-Fi connection for ~2 minutes
# (new location, changed router password, first run without dietpi-wifi.txt),
# it raises its own access point with a captive portal pointing at the control
# panel, so any phone can hand it the local Wi-Fi credentials:
#
#   no Wi-Fi for DOWN_LIMIT checks
#     -> snapshot a Wi-Fi scan (the panel serves it from cache in AP mode)
#     -> ifdown + static IP + hostapd + dnsmasq (DHCP, DNS catch-all)
#     -> phone joins "Synchrofazotron-Setup", portal opens the panel
#     -> user saves a network in /settings (writes the DietPi Wi-Fi db)
#     -> db change detected -> AP torn down -> normal Wi-Fi (ifup) retried
#     -> still nothing after the retry window -> the cycle repeats
#
# The AP also times out on its own (AP_WINDOW) so a transient outage does not
# leave the device stuck in setup mode forever.
set -u

IFACE="${PISTREAM_WIFI_IFACE:-wlan0}"
PANEL_PORT="${PISTREAM_PANEL_PORT:-8787}"
AP_IP=192.168.4.1
CHECK_EVERY=10        # seconds between connectivity checks
DOWN_LIMIT=12         # failed checks in a row before the AP comes up (12*10 s = 2 min)
AP_WINDOW=600         # how long the AP waits for configuration (10 min)
STA_RETRY=120         # after the AP: how long to retry normal Wi-Fi before giving up
DIR=/opt/pistream-ap
MARKER=/run/pistream-ap.active
SCAN_CACHE=/run/pistream-ap-scan.json
WIFI_DB=/var/lib/dietpi/dietpi-wifi.db
HOSTAPD_PID=/run/pistream-hostapd.pid
DNSMASQ_PID=/run/pistream-dnsmasq.pid

connected() {
    iw dev "$IFACE" link 2>/dev/null | grep -q '^Connected to'
}

db_mtime() { stat -c %Y "$WIFI_DB" 2>/dev/null || echo 0; }

ap_up() {
    echo "No Wi-Fi — raising the setup AP"
    # Snapshot the neighborhood while the radio can still scan; in AP mode the
    # shared radio cannot, so the panel serves this file instead (see
    # _wifi_scan_networks in the panel).
    curl -sf -m 30 "http://127.0.0.1:$PANEL_PORT/api/wifi/scan" -o "$SCAN_CACHE" || true
    ifdown "$IFACE" 2>/dev/null || true
    pkill -f "wpa_supplicant.*$IFACE" 2>/dev/null || true
    ip addr flush dev "$IFACE" 2>/dev/null || true
    ip link set "$IFACE" up
    ip addr add "$AP_IP/24" dev "$IFACE"
    if ! hostapd -B -P "$HOSTAPD_PID" "$DIR/hostapd.conf"; then
        echo "hostapd failed to start — aborting this AP attempt"
        ap_down
        return 1
    fi
    dnsmasq --conf-file="$DIR/dnsmasq.conf" --pid-file="$DNSMASQ_PID" \
        || echo "dnsmasq failed (no DHCP/portal — clients need manual IP 192.168.4.x)"
    # Captive portal: any http:// address the phone probes lands on the panel.
    iptables -t nat -A PREROUTING -i "$IFACE" -p tcp --dport 80 \
        -j REDIRECT --to-port "$PANEL_PORT" 2>/dev/null || true
    touch "$MARKER"
    echo "Setup AP up: connect to it and open http://$AP_IP (portal should pop up on its own)"
}

ap_down() {
    [[ -e $MARKER ]] || return 0
    echo "Tearing the setup AP down — back to normal Wi-Fi"
    rm -f "$MARKER"
    iptables -t nat -D PREROUTING -i "$IFACE" -p tcp --dport 80 \
        -j REDIRECT --to-port "$PANEL_PORT" 2>/dev/null || true
    [[ -f $DNSMASQ_PID ]] && kill "$(cat "$DNSMASQ_PID")" 2>/dev/null
    [[ -f $HOSTAPD_PID ]] && kill "$(cat "$HOSTAPD_PID")" 2>/dev/null
    rm -f "$DNSMASQ_PID" "$HOSTAPD_PID"
    # stragglers (match on our config paths only — never a system dnsmasq)
    pkill -f "$DIR/hostapd.conf" 2>/dev/null || true
    pkill -f "$DIR/dnsmasq.conf" 2>/dev/null || true
    sleep 1
    ip addr flush dev "$IFACE" 2>/dev/null || true
    ifup "$IFACE" 2>/dev/null || true
}

trap ap_down EXIT

# `net-watch.sh cleanup` — used by ExecStopPost so a killed service never
# leaves the AP (and the hijacked interface) behind.
if [[ "${1:-}" == cleanup ]]; then
    exit 0   # the EXIT trap does the actual work
fi

ap_cycle() {
    ap_up || return 0
    local started db0
    started=$(date +%s)
    db0=$(db_mtime)
    while :; do
        sleep 5
        if [[ "$(db_mtime)" != "$db0" ]]; then
            echo "Wi-Fi config changed via the panel — trying to connect"
            sleep 2   # let the panel finish writing/applying the db
            break
        fi
        if (( $(date +%s) - started >= AP_WINDOW )); then
            echo "AP window expired with no configuration — retrying normal Wi-Fi"
            break
        fi
    done
    ap_down
    local t0
    t0=$(date +%s)
    while (( $(date +%s) - t0 < STA_RETRY )); do
        if connected; then
            echo "Connected."
            return 0
        fi
        sleep 5
    done
    echo "Still no Wi-Fi after the retry window (the main loop will re-enter AP mode)"
}

down=0
while :; do
    if connected; then
        down=0
    else
        down=$((down + 1))
        if (( down >= DOWN_LIMIT )); then
            ap_cycle
            down=0
        fi
    fi
    sleep "$CHECK_EVERY"
done
