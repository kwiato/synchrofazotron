# pc — wake a PC from Synchrofazotron

Wake-on-LAN for a computer on the same LAN, ported from
[pimote](https://github.com/kwiato/pimote) (the wake half; pimote's USB
keyboard needs a cable to the PC and is a separate plugin).

```bash
curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/web/plugins/pc/install.sh | sudo bash
```

Then **Settings → Plugins → PC**: enter the PC's Ethernet MAC (Windows:
`ipconfig /all` → *Physical Address*), optionally its IP for the up/down
pill, save, and the **Wake PC** button is live.

## How it works

- The magic packet (6×`FF` + MAC×16) goes out as a UDP broadcast to
  `255.255.255.255:9` and `:7` — plain socket, no `wakeonlan` package. WoL is
  L2 broadcast, so the Pi and the PC must share the LAN (Wi-Fi on the Pi is
  fine as long as the router bridges it to the wired segment the PC is on).
- The status pill pings the configured host once per poll while the card is
  open (`ping -c1 -W1`); no host → no pill.
- Config: `/opt/pistream-panel/plugins-data/pc/config.json` (`mac`, `host`).
  Survives updates and uninstall (`uninstall.sh --purge` drops it).

## PC side

Same as pimote's README — the usual reasons WoL does not fire:

- BIOS: *ErP Ready = Disabled*, *Resume By PCI-E/Networking Device = Enabled*
- Windows: **Fast startup off** (Power Options → what the power buttons do),
  adapter → Advanced → *Wake on Magic Packet = Enabled*, power management →
  allow wake only via magic packet
- Works from S3 (sleep) and S5 (shutdown); S4 (hibernation) is flaky on MSI
- If waking from S5 fails, the vendor LAN driver is usually the fix

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/p/pc/state` | `{mac, host, online: true\|false\|null, last_wake}` |
| POST | `/api/p/pc/wake` | send the magic packet |
| POST | `/api/p/pc/config` | `{"mac": "…", "host": "…"}` |

Handy for automation (a Glance tile, a shortcut): `curl -X POST http://<pi>:8787/api/p/pc/wake`.
The panel has no authentication — keep it on Tailscale, as always.
