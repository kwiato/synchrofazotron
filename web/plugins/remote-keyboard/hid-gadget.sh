#!/bin/bash
# Synchrofazotron plugin "remote-keyboard": build the USB HID keyboard gadget
# via configfs and bind it to the Pi's USB controller. Run at boot by
# synchrofazotron-hid-gadget.service (installed by the plugin's install.sh). Needs
# dtoverlay=dwc2,dr_mode=peripheral in config.txt (also install.sh's job).
# From pimote's usr-local-bin/hid-gadget.sh, minus the owner handling: the
# panel runs as root, so /dev/hidg0 stays root-only (0600).
set -e
modprobe libcomposite
cd /sys/kernel/config/usb_gadget/
G=synchrofazotron
if [ -d "$G" ] && [ -s "$G/UDC" ]; then
  echo "gadget $G already bound"; exit 0
fi
mkdir -p "$G"
cd "$G"

echo 0x1d6b > idVendor   # Linux Foundation
echo 0x0104 > idProduct  # Multifunction Composite Gadget
echo 0x0100 > bcdDevice  # v1.0.0
echo 0x0200 > bcdUSB     # USB 2.0

mkdir -p strings/0x409
echo "fedcba9876543210"      > strings/0x409/serialnumber
echo "Synchrofazotron"       > strings/0x409/manufacturer
echo "Synchrofazotron Keyboard" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo "Config 1: Keyboard" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

# HID function: boot-protocol keyboard, 8-byte reports
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
echo -ne \\x05\\x01\\x09\\x06\\xa1\\x01\\x05\\x07\\x19\\xe0\\x29\\xe7\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x08\\x81\\x02\\x95\\x01\\x75\\x08\\x81\\x03\\x95\\x05\\x75\\x01\\x05\\x08\\x19\\x01\\x29\\x05\\x91\\x02\\x95\\x01\\x75\\x03\\x91\\x03\\x95\\x06\\x75\\x08\\x15\\x00\\x25\\x65\\x05\\x07\\x19\\x00\\x29\\x65\\x81\\x00\\xc0 > functions/hid.usb0/report_desc

[ -e configs/c.1/hid.usb0 ] || ln -s functions/hid.usb0 configs/c.1/

# bind to the USB device controller (empty when the overlay is not active)
UDC="$(ls /sys/class/udc | head -1)"
[ -n "$UDC" ] || { echo "no UDC in /sys/class/udc: is dtoverlay=dwc2,dr_mode=peripheral set and the Pi rebooted?" >&2; exit 1; }
echo "$UDC" > UDC
chmod 600 /dev/hidg0
