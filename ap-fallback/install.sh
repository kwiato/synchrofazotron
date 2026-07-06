#!/bin/bash
# Synchrofazotron setup-AP fallback — install / update.
#
#   curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/ap-fallback/install.sh | sudo bash
#
# What it does:
#   1) installs hostapd + dnsmasq (their global services stay disabled — the
#      binaries are only ever started by net-watch.sh with our own configs)
#   2) installs net-watch.sh + configs to /opt/pistream-ap
#   3) enables the pistream-net-watch service (permanent Wi-Fi watchdog)
# To undo: uninstall.sh from the same repo directory.
set -euo pipefail

REPO="${PISTREAM_REPO:-kwiato/synchrofazotron}"
BRANCH="${PISTREAM_BRANCH:-main}"
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH/ap-fallback"
FILES=(net-watch.sh hostapd.conf dnsmasq.conf pistream-net-watch.service)
DEST=/opt/pistream-ap

SRC_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo .)"
if [[ "$(basename -- "$0")" != "install.sh" || ! -f "$SRC_DIR/net-watch.sh" ]]; then
  echo "==> Downloading $REPO@$BRANCH from GitHub"
  SRC_DIR="$(mktemp -d)"
  trap 'rm -rf "$SRC_DIR"' EXIT
  for f in "${FILES[@]}"; do
    curl -fsSL --retry 5 --retry-delay 2 "$RAW/$f" -o "$SRC_DIR/$f"
  done
fi

echo "==> Installing hostapd + dnsmasq"
for pkg in hostapd dnsmasq; do
  dpkg -s "$pkg" >/dev/null 2>&1 || DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg"
done
# The Debian packages ship global services (dnsmasq even auto-starts as a
# system-wide DNS). We run the binaries ourselves — keep the services off.
systemctl disable --now dnsmasq 2>/dev/null || true
systemctl disable --now hostapd 2>/dev/null || true

echo "==> Installing net-watch to $DEST"
install -d "$DEST"
install -m 0755 "$SRC_DIR/net-watch.sh" "$DEST/net-watch.sh"
# keep a locally edited hostapd.conf (custom SSID/password) on update
if [[ -f "$DEST/hostapd.conf" ]] && ! cmp -s "$SRC_DIR/hostapd.conf" "$DEST/hostapd.conf"; then
  echo "    keeping existing (edited) hostapd.conf — new default saved as hostapd.conf.new"
  install -m 0600 "$SRC_DIR/hostapd.conf" "$DEST/hostapd.conf.new"
else
  install -m 0600 "$SRC_DIR/hostapd.conf" "$DEST/hostapd.conf"
fi
install -m 0644 "$SRC_DIR/dnsmasq.conf" "$DEST/dnsmasq.conf"
install -m 0644 "$SRC_DIR/pistream-net-watch.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable pistream-net-watch.service
systemctl restart pistream-net-watch.service

echo
echo "==> Done. If the device has no Wi-Fi for ~2 minutes, it raises the AP:"
echo "    SSID: $(grep -oP '^ssid=\K.*' "$DEST/hostapd.conf")   password: $(grep -oP '^wpa_passphrase=\K.*' "$DEST/hostapd.conf")"
echo "    Then connect a phone to it — the setup page opens as a captive portal"
echo "    (or go to http://192.168.4.1)."
