#!/bin/bash
# Synchrofazotron plugin "pc" — install / update.
#
#   curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/web/plugins/pc/install.sh | sudo bash
#
# Copies the plugin into /opt/pistream-panel/plugins/pc and restarts the panel
# (which loads plugins at boot). Settings live in plugins-data/pc/ and survive
# both updates and uninstall. Needs nothing beyond the panel itself: the magic
# packet is sent with a plain socket, the status check uses the system ping.
set -euo pipefail

REPO="${PISTREAM_REPO:-kwiato/synchrofazotron}"
BRANCH="${PISTREAM_BRANCH:-main}"
PLUGIN=pc
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH/web/plugins/$PLUGIN"
FILES=(plugin.json plugin.py ui.js)
PANEL=/opt/pistream-panel
DEST="$PANEL/plugins/$PLUGIN"

[[ -f $PANEL/pistream_panel.py ]] || {
  echo "ERROR: the panel is not installed in $PANEL (run web/install.sh first)"; exit 1; }

SRC_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo .)"
if [[ "$(basename -- "$0")" != "install.sh" || ! -f "$SRC_DIR/plugin.json" ]]; then
  echo "==> Downloading plugin $PLUGIN ($REPO@$BRANCH)"
  SRC_DIR="$(mktemp -d)"
  trap 'rm -rf "$SRC_DIR"' EXIT
  for f in "${FILES[@]}"; do
    curl -fsSL --retry 5 --retry-delay 2 "$RAW/$f" -o "$SRC_DIR/$f"
  done
fi

echo "==> Installing to $DEST"
install -d "$DEST"
for f in "${FILES[@]}"; do
  install -m 0644 "$SRC_DIR/$f" "$DEST/$f"
done

echo "==> Restarting the panel"
systemctl restart pistream-panel.service
echo "==> Done: Settings > Plugins > PC"
