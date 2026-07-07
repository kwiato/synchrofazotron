# Synchrofazotron control panel

A lightweight microservice (Python, stdlib only — no dependencies) serving a
mobile HTML page for controlling the Synchrofazotron audio player. Meant to be exposed
over Tailscale.

## What it does

- **"Enable Bluetooth pairing" button** — makes the adapter `discoverable` and
  `pairable` for 180 s. Auto-accepting the pairing ("Just Works", no
  confirmation on the Pi side) is handled by a separate persistent
  **`bt-agent -c NoInputNoOutput`** service (`bluez-tools` package, installed
  by `install.sh`). The panel additionally marks connected devices as `trust`ed
  so they reconnect on their own.
- **Instructions** for how and what to play: Bluetooth, Spotify Connect,
  AirPlay, TIDAL/radio/library via Lyrion Music Server.
- Live status view (BT ready/pairing, connected devices, service states).
- **"Now playing"** — which sources are currently playing (LMS via jsonrpc,
  Bluetooth via `bluealsa-cli`, AirPlay/Spotify via ALSA busy state) + a warning
  when several play at once.
- **Play/pause buttons** per source (on the right):
  - **LMS** — jsonrpc,
  - **Bluetooth** — AVRCP via BlueZ `MediaPlayer1` (pauses the source phone),
  - **AirPlay** — MPRIS (`org.mpris.MediaPlayer2.ShairportSync`),
  - **Spotify** — no local control (librespot); pause from the Spotify app.
- **Auto-pause arbiter** ("new playback wins") — a background loop: when a new
  source starts playing, the previously playing one is paused via the same
  control paths as above. Needed on a hardware DAC, where only one source can
  hold the output (on HDMI audio sources simply mix). For Bluetooth it also
  restarts `bluealsa-aplay` once the device frees up, because bluealsa-aplay
  does not retry after failing to open a busy device. Works together with
  `squeezelite -C 5` (set by `setup.sh`) — without it a *paused* LMS holds the
  DAC forever. Disable with `PISTREAM_AUTOPAUSE=0`.
- **Two UI languages** — English and Polish, switchable in `/settings`
  (persisted on the device; default via `PISTREAM_LANG`).

## Install & update (on the Pi)

Straight from GitHub (install and update are the same command — fetches the
latest version and restarts the services):

```bash
curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/web/install.sh | sudo bash
```

Or locally (files copied to the Pi):

```bash
sudo bash install.sh
```

The panel starts as the `pistream-panel` service (autostart at boot) on port
**8787**.

Access:
- Tailscale: `http://<tailscale-ip>:8787` or `http://pistream:8787` (MagicDNS)
- LAN: `http://<lan-ip>:8787`

## Local UI preview (development)

The panel is stdlib-only Python, so it runs on any machine (Windows/macOS/
Linux) without a Pi:

```bash
python web/pistream_panel.py
# then open http://127.0.0.1:8787  (panel) and /settings
```

Anything launched from outside `/opt/pistream-panel` (i.e. a repo checkout,
on any OS) starts in **sandbox mode**: every system command is a no-op, so
previewing the UI can never change the host — no hostname, tailscale,
`systemctl`, bluetooth or reboot/update actions run. The startup line says
`sandbox mode` when it is on. Force it either way with `PISTREAM_DEV=1`/`0`
(the installed service runs from `/opt/...`, so it defaults to real mode).

In sandbox mode the pages render with empty/degraded data — services show
red, sources are silent, the visualizer card says "not installed". That is
fine for working on layout/CSS/JS. Notes:

- The UI lives in **`web/ui/`** and is read from disk on every request:
  edit a file, refresh the browser — no server restart needed.
  - `ui/panel.html` + `ui/panel.js` — main page (tabs, player bar)
  - `ui/settings.html` + `ui/settings.js` — settings page
  - `ui/style.css` — shared stylesheet (both pages)
- HTML and JS are served through the i18n filler: `{{T:key}}` placeholders
  (strings live in the `STR` dict in `pistream_panel.py`), plus `{{DEVICE}}`,
  `{{LANG}}`, `{{LMS_URL}}`, `{{LMS_PORT}}`, `{{PAIR_WIN}}`, `{{PLAYER}}`.
  CSS is served raw.
- Switching the language or the device name in `/settings` writes a `lang` /
  `name` file next to the script (both gitignored — they hold the runtime
  choice and survive updates).
- Buttons that talk to the system (reboot, Wi-Fi save, pairing) are safe to
  click locally: the underlying commands just fail and the UI shows an error.

## Configuration

Everything via environment variables (set in `pistream-panel.service`),
with sensible defaults:

| Env | Default | Description |
|---|---|---|
| `PISTREAM_NAME` | hostname | device name shown in the panel |
| `PISTREAM_LMS_PLAYER` | hostname | Squeezelite player name in LMS |
| `PISTREAM_SPOTIFY` | `0` | `1` = show the Spotify section (when raspotify is installed) |
| `PISTREAM_WIFI_IFACE` | `wlan0` | Wi-Fi interface for the settings page |
| `PISTREAM_LANG` | `en` | default UI language (`en`/`pl`); runtime choice from `/settings` wins |
| `PISTREAM_AUTOPAUSE` | `1` | `0` = do not auto-pause the previous source when a new one starts |
| `PISTREAM_PANEL_PORT` | `8787` | HTTP port |
| `PISTREAM_PANEL_BIND` | `0.0.0.0` | bind address |
| `PISTREAM_DEV` | auto | `1` = sandbox (no system commands run); `0` = run for real. Default: real only when launched from `/opt/pistream-panel`, sandbox otherwise |

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | panel page (tabs: now playing / visualizer, player bar) |
| GET | `/settings` | settings page (config, sources, visualizer, about) |
| GET | `/studio` | shader studio (when `visualizer-studio.html` is installed) |
| GET | `/api/tailscale` | JSON: tailscale installed/active/ip |
| POST | `/api/tailscale/set` | `{"up":true\|false}` — tailscale up / down |
| GET | `/api/sources` | JSON: source groups (installed/enabled + per-service state) |
| POST | `/api/source/toggle` | `{"source":"bluetooth\|airplay\|lms\|spotify","enable":bool}` |
| POST | `/api/bt/forget` | `{"mac":"..."}` — removes the pairing |
| POST | `/api/name` | `{"name":"..."}` — renames the device (hostname, BT alias, AirPlay/LMS) |
| GET | `/api/status` | JSON: BT state, connected devices, active sources, services |
| GET | `/api/wifi` | JSON: current connection + saved networks (no passwords) |
| GET | `/api/wifi/scan` | JSON: networks in range |
| GET | `/api/lang` | JSON: current + available UI languages |
| POST | `/api/pair` | opens the BT pairing window |
| POST | `/api/control` | `{"source":"lms\|bt\|airplay","action":"toggle\|play\|pause"}` |
| POST | `/api/wifi/add` | `{"ssid":"...","key":"..."}` — writes to the DietPi db + reload |
| POST | `/api/wifi/remove` | `{"slot":n}` — removal (the current network is blocked) |
| POST | `/api/lang` | `{"lang":"en"\|"pl"}` — switches the UI language |

## Wi-Fi settings — how it works

The `/settings` page writes networks into the DietPi database
(`/var/lib/dietpi/dietpi-wifi.db`, the same slots `dietpi-config` uses),
regenerates `wpa_supplicant.conf` via `dietpi-wifidb 1` and reloads the
configuration on the fly (`wpa_cli reconfigure`) — no reboot and no dropping
the current connection. You can add a network that is out of range (e.g. the
home network before moving the device).

In setup-AP mode (see `../ap-fallback/`) `/api/wifi/scan` serves the snapshot
taken just before the AP went up — the shared radio cannot scan while being
an AP. Saving a network then also tells the watchdog to tear the AP down and
join it.

## Notes

- The service runs as **root** (required by `bluetoothctl` for agent and
  visibility control). BT audio goes to the ALSA `default` output via
  `bluealsa-aplay`.
- Expose the panel over **Tailscale**, not to the public internet — the
  endpoints have no authentication and `/api/wifi/add` accepts network
  passwords (inside the tailnet the traffic is encrypted; on the open internet
  it would be plain HTTP).
- The Spotify section is hidden by default (`PISTREAM_SPOTIFY=0`) — raspotify
  deliberately skipped in the 2026-07 install.
- Audio goes out through the DAC (BossDAC, `allo-boss-dac-pcm512x-audio`
  overlay); the story of the HDMI workaround lives in `../dac-setup.md`.
