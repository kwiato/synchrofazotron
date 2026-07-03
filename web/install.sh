#!/bin/bash
# Instalacja / aktualizacja PiStream control panel jako usługi systemd.
#
# Dwa tryby:
#   1) lokalnie (pliki obok skryptu):   sudo bash install.sh
#   2) prosto z GitHuba (instalacja LUB update):
#        curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/web/install.sh | sudo bash
set -euo pipefail

REPO="${PISTREAM_REPO:-kwiato/synchrofazotron}"
BRANCH="${PISTREAM_BRANCH:-main}"
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH/web"
FILES=(pistream_panel.py pistream-panel.service bt-agent.service)
DEST=/opt/pistream-panel

SRC_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo .)"
if [[ ! -f "$SRC_DIR/pistream_panel.py" ]]; then
  echo "==> Brak plików lokalnie — pobieram $REPO@$BRANCH z GitHuba"
  SRC_DIR="$(mktemp -d)"
  trap 'rm -rf "$SRC_DIR"' EXIT
  for f in "${FILES[@]}"; do
    curl -fsSL "$RAW/$f" -o "$SRC_DIR/$f"
  done
fi

echo "==> Instalacja bt-agent (headless auto-akceptacja parowania BT)"
if ! command -v bt-agent >/dev/null 2>&1; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y bluez-tools
fi
install -m 0644 "$SRC_DIR/bt-agent.service" /etc/systemd/system/bt-agent.service

echo "==> Kopiowanie panelu do $DEST"
install -d "$DEST"
install -m 0755 "$SRC_DIR/pistream_panel.py" "$DEST/pistream_panel.py"

echo "==> Instalacja usług systemd"
install -m 0644 "$SRC_DIR/pistream-panel.service" /etc/systemd/system/pistream-panel.service
systemctl daemon-reload
systemctl enable bt-agent.service pistream-panel.service
# restart (nie enable --now): przy update podmienia działający proces na nowy kod
systemctl restart bt-agent.service pistream-panel.service

sleep 1
systemctl --no-pager --full status pistream-panel.service | head -n 8 || true

IP="$(tailscale ip -4 2>/dev/null | head -n1 || true)"
PORT="$(grep -oP 'PISTREAM_PANEL_PORT=\K[0-9]+' /etc/systemd/system/pistream-panel.service || echo 8787)"
echo
echo "==> Gotowe. Panel dostępny pod:"
[ -n "$IP" ] && echo "    http://$IP:$PORT        (Tailscale)"
echo "    http://$(hostname):$PORT   (MagicDNS / LAN)"
