#!/bin/bash
# Synchrofazotron plugin "remote-keyboard" — remove.
#
#   curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/web/plugins/remote-keyboard/uninstall.sh | sudo bash
#
# Drops the plugin folder, the gadget boot service and the dwc2 overlay line
# from config.txt (the USB port goes back to host mode on the next boot; the
# gadget built in this boot stays until then). Settings in
# plugins-data/remote-keyboard/ are kept (add --purge to remove them too).
set -euo pipefail

PANEL=/opt/pistream-panel
PLUGIN=remote-keyboard
OVERLAY="dtoverlay=dwc2,dr_mode=peripheral"

rm -rf "$PANEL/plugins/$PLUGIN"
if [[ "${1:-}" == "--purge" ]]; then
  rm -rf "$PANEL/plugins-data/$PLUGIN"
fi

systemctl disable --now synchrofazotron-hid-gadget.service 2>/dev/null || true
rm -f /etc/systemd/system/synchrofazotron-hid-gadget.service /usr/local/bin/synchrofazotron-hid-gadget.sh
systemctl daemon-reload 2>/dev/null || true

for p in /boot/firmware/config.txt /boot/config.txt; do
  [[ -f "$p" ]] || continue
  sed -i -e '/^# remote-keyboard plugin: USB port in device mode (HID keyboard)$/d' \
         -e "/^${OVERLAY}$/d" "$p"
  break
done

systemctl restart pistream-panel.service 2>/dev/null || true
echo "==> Plugin $PLUGIN removed (reboot to return the USB port to host mode)"
