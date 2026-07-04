#!/bin/bash
# Install / update the Synchrofazotron control panel as a systemd service.
#
# Two modes:
#   1) locally (files next to the script):   sudo bash install.sh
#   2) straight from GitHub (install OR update):
#        curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/web/install.sh | sudo bash
set -euo pipefail

REPO="${PISTREAM_REPO:-kwiato/synchrofazotron}"
BRANCH="${PISTREAM_BRANCH:-main}"
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH/web"
FILES=(pistream_panel.py pistream-panel.service bt-agent.service)
DEST=/opt/pistream-panel

# Local mode ONLY when the script was run as a file (bash install.sh).
# With `curl | bash` $0 is "bash" — then we always download from GitHub, even
# if (stale) panel files happen to be lying around in the current directory.
SRC_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo .)"
if [[ "$(basename -- "$0")" != "install.sh" || ! -f "$SRC_DIR/pistream_panel.py" ]]; then
  echo "==> Downloading $REPO@$BRANCH from GitHub"
  SRC_DIR="$(mktemp -d)"
  trap 'rm -rf "$SRC_DIR"' EXIT
  for f in "${FILES[@]}"; do
    curl -fsSL "$RAW/$f" -o "$SRC_DIR/$f"
  done
fi

echo "==> Installing bt-agent (headless auto-accept for BT pairing)"
if ! command -v bt-agent >/dev/null 2>&1; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y bluez-tools
fi
install -m 0644 "$SRC_DIR/bt-agent.service" /etc/systemd/system/bt-agent.service

echo "==> Copying the panel to $DEST"
install -d "$DEST"
install -m 0755 "$SRC_DIR/pistream_panel.py" "$DEST/pistream_panel.py"

echo "==> Installing systemd services"
install -m 0644 "$SRC_DIR/pistream-panel.service" /etc/systemd/system/pistream-panel.service
systemctl daemon-reload
systemctl enable bt-agent.service pistream-panel.service
# restart (not enable --now): on update this swaps the running process for the new code
systemctl restart bt-agent.service pistream-panel.service

sleep 1
systemctl --no-pager --full status pistream-panel.service | head -n 8 || true

IP="$(tailscale ip -4 2>/dev/null | head -n1 || true)"
PORT="$(grep -oP 'PISTREAM_PANEL_PORT=\K[0-9]+' /etc/systemd/system/pistream-panel.service || echo 8787)"
echo
echo "==> Done. Panel available at:"
[ -n "$IP" ] && echo "    http://$IP:$PORT        (Tailscale)"
echo "    http://$(hostname):$PORT   (MagicDNS / LAN)"
