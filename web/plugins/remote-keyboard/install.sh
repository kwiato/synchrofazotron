#!/bin/bash
# Synchrofazotron plugin "remote-keyboard" — install / update.
#
#   curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/web/plugins/remote-keyboard/install.sh | sudo bash
#
# Copies the plugin into /opt/pistream-panel/plugins/remote-keyboard, sets up
# the USB HID gadget (dwc2 overlay in config.txt + a boot service that builds
# the gadget in configfs) and restarts the panel. The overlay takes effect on
# the next boot, so the FIRST install ends with "reboot needed"; the card in
# Settings > Plugins says the same until then. Settings live in
# plugins-data/remote-keyboard/ and survive updates and uninstall.
set -euo pipefail

REPO="${PISTREAM_REPO:-kwiato/synchrofazotron}"
BRANCH="${PISTREAM_BRANCH:-main}"
PLUGIN=remote-keyboard
RAW="https://raw.githubusercontent.com/$REPO/$BRANCH/web/plugins/$PLUGIN"
FILES=(plugin.json plugin.py ui.js style.css hid-gadget.sh hid-gadget.service)
PANEL=/opt/pistream-panel
DEST="$PANEL/plugins/$PLUGIN"
GADGET_BIN=/usr/local/bin/synchrofazotron-hid-gadget.sh
GADGET_UNIT=/etc/systemd/system/synchrofazotron-hid-gadget.service
OVERLAY="dtoverlay=dwc2,dr_mode=peripheral"

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

# --- USB gadget: overlay ------------------------------------------------------
# config.txt path differs between Pi OS / DietPi versions.
BOOT_CFG=""
for p in /boot/firmware/config.txt /boot/config.txt; do
  [[ -f "$p" ]] && { BOOT_CFG="$p"; break; }
done
NEED_REBOOT=0
if [[ -z "$BOOT_CFG" ]]; then
  echo "WARNING: config.txt not found; add '$OVERLAY' to it by hand"
elif grep -qx "$OVERLAY" "$BOOT_CFG"; then
  echo "==> $BOOT_CFG: overlay already set"
else
  printf '\n# remote-keyboard plugin: USB port in device mode (HID keyboard)\n%s\n' "$OVERLAY" >> "$BOOT_CFG"
  echo "==> $BOOT_CFG: added $OVERLAY"
  NEED_REBOOT=1
fi

# --- USB gadget: boot service -------------------------------------------------
# pimote's own gadget unit would fight for the one UDC; there can be one.
if systemctl is-enabled hid-gadget.service >/dev/null 2>&1; then
  echo "WARNING: pimote's hid-gadget.service is enabled on this device; run pimote's uninstall.sh first"
fi
install -m 0755 "$SRC_DIR/hid-gadget.sh" "$GADGET_BIN"
install -m 0644 "$SRC_DIR/hid-gadget.service" "$GADGET_UNIT"
systemctl daemon-reload
systemctl enable synchrofazotron-hid-gadget.service >/dev/null 2>&1 || true
if [[ "$NEED_REBOOT" -eq 0 ]]; then
  systemctl restart synchrofazotron-hid-gadget.service \
    || echo "WARNING: hid-gadget.service did not start (journalctl -u synchrofazotron-hid-gadget); a reboot usually fixes it"
fi

echo "==> Restarting the panel"
systemctl restart pistream-panel.service
if [[ "$NEED_REBOOT" -eq 1 ]]; then
  echo "==> Done. REBOOT the device once to activate the USB gadget, then: Settings > Plugins > Remote Keyboard"
else
  echo "==> Done: Settings > Plugins > Remote Keyboard"
fi
