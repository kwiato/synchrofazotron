# remote-keyboard — type on the PC from Synchrofazotron

The device becomes a USB keyboard plugged into the PC (a HID gadget on the
Pi's USB port), and the panel gets a card that types text and presses keys
there. The keyboard half of [pimote](https://github.com/kwiato/pimote); the
wake half is the [`pc`](../pc/) plugin.

```bash
curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/web/plugins/remote-keyboard/install.sh | sudo bash
sudo reboot   # first install only: activates the USB gadget overlay
```

Then **Settings → Plugins → Remote Keyboard**: a text field with **Send**
(types the text into whatever has focus on the PC; Enter in the field sends
too), **Backspace** and **Enter** buttons, and **More keys…** with the arrows,
Esc and Del. The pill in the card head says whether the PC currently sees the
keyboard.

## Hardware

- Raspberry Pi Zero 2 W: the **USB** port (middle one, next to HDMI) goes to
  the PC with a cable that has data lines; the **PWR** port keeps its charger.
  Mixing them up is the classic failure: the PC powers the Pi but never sees a
  keyboard.
- If pimote itself is installed on this Pi, uninstall it first: two gadgets
  cannot share the one USB controller.
- The overlay puts the port in device mode, so nothing USB-host (a dongle, a
  USB DAC) can share it. The DAC HAT and on-board Wi-Fi are unaffected.

## How it works

- `install.sh` appends `dtoverlay=dwc2,dr_mode=peripheral` to `config.txt`
  and installs `synchrofazotron-hid-gadget.service`, which at boot builds the gadget in
  configfs (`/sys/kernel/config/usb_gadget/synchrofazotron`, a boot-protocol
  keyboard with 8-byte reports) and binds it to the UDC. Result: `/dev/hidg0`,
  root-only.
- `plugin.py` writes reports there: `[modifiers, 0, key, 0, 0, 0, 0, 0]` then
  eight zeros to release. Codes are USB HID usages, so they do not depend on
  the layout; the layout Windows has active decides what each (modifier, key)
  pair produces. The plugin knows two: **Polish (Programmers)** (default: US
  keys, ą/ć/ł… as AltGr + letter) and **US**. Characters the layout cannot
  make are skipped and counted in the reply. Writes are non-blocking with a
  half-second wait per report, so a PC that is off or not enumerating the
  gadget gives a "no PC" answer instead of a hung panel.
- Status (`GET /state`): `ready` when `/sys/class/udc/*/state` says
  `configured`, `no_pc` when the device exists but the PC has not enumerated
  it, `reboot` when the overlay is in `config.txt` but `/dev/hidg0` is not
  there yet, `no_gadget` when neither is, `sandbox` in a repo checkout.
- Config: `/opt/pistream-panel/plugins-data/remote-keyboard/config.json`
  (`layout`). Survives updates and uninstall (`uninstall.sh --purge` drops it).

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/p/remote-keyboard/state` | `{status, udc, layout}` |
| POST | `/api/p/remote-keyboard/type` | `{"text": "…"}` (≤ 2000 chars; `\n` = Enter) → `{ok, typed, skipped}` |
| POST | `/api/p/remote-keyboard/key` | `{"key": "enter", "mods": ["ctrl"]}`, names as in `plugin.py` (`KEYS`, `MOD`) |
| POST | `/api/p/remote-keyboard/config` | `{"layout": "pl" \| "us"}` |

Handy for automation: `curl -X POST http://<pi>:8787/api/p/remote-keyboard/type -d '{"text":"hello\n"}'`.
The panel has no authentication and this plugin types into the PC: keep it on
Tailscale, never on an open LAN.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| pill says *reboot needed* | first install; `sudo reboot` |
| pill says *no gadget* | `journalctl -u synchrofazotron-hid-gadget`; overlay missing from `config.txt`, or `libcomposite` did not load |
| pill says *no PC* | cable in PWR instead of USB, charge-only cable, PC off; `cat /sys/class/udc/*/state` should say `configured` |
| wrong characters on the PC | layout mismatch: set the same layout in the card as Windows uses (Polish 214 is not supported) |
| `Cannot send after transport endpoint shutdown` in the log | the PC stopped polling mid-write (sleep, unplugged); try again |

Force USB re-enumeration without a reboot:
```bash
echo "" | sudo tee /sys/kernel/config/usb_gadget/synchrofazotron/UDC
ls /sys/class/udc/ | sudo tee /sys/kernel/config/usb_gadget/synchrofazotron/UDC
```
