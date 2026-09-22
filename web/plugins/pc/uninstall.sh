#!/bin/bash
# Synchrofazotron plugin "pc" — remove.
#
#   curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/web/plugins/pc/uninstall.sh | sudo bash
#
# Drops the plugin folder and restarts the panel. Settings in plugins-data/pc/
# are kept (add --purge to remove them too).
set -euo pipefail

PANEL=/opt/pistream-panel
PLUGIN=pc

rm -rf "$PANEL/plugins/$PLUGIN"
if [[ "${1:-}" == "--purge" ]]; then
  rm -rf "$PANEL/plugins-data/$PLUGIN"
fi
systemctl restart pistream-panel.service 2>/dev/null || true
echo "==> Plugin $PLUGIN removed"
