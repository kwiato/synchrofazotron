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

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | panel page |
| GET | `/settings` | settings page (Wi-Fi, visualizer, language) |
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
