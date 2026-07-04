#!/bin/bash
# Synchrofazotron setup-AP fallback — full uninstall.
#   curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/ap-fallback/uninstall.sh | sudo bash
set -euo pipefail

echo "==> Stopping and removing the net-watch service"
# stop first: ExecStopPost tears the AP down if it happens to be up right now
systemctl disable --now pistream-net-watch.service 2>/dev/null || true
rm -f /etc/systemd/system/pistream-net-watch.service
rm -rf /opt/pistream-ap
rm -f /run/pistream-ap.active /run/pistream-ap-scan.json
systemctl daemon-reload

echo "==> Done. hostapd/dnsmasq packages left installed (apt remove hostapd dnsmasq if unwanted)."
