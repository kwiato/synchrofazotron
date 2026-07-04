# Synchrofazotron

A self-contained, headless audio streamer built on a Raspberry Pi Zero 2 W and
DietPi. One box that plays everything the household throws at it:

- **TIDAL / internet radio / library** — Lyrion Music Server (LMS) + Squeezelite,
  controlled from the Squeezer (Android) / iPeng (iOS) apps or the Material web UI
- **AirPlay** — Shairport Sync
- **Bluetooth A2DP** — bluez-alsa, with one-tap pairing from the web panel
- **Spotify Connect** — raspotify (optional, off by default)
- **Web control panel** — mobile page for pairing, Wi-Fi setup and play/pause,
  meant to be exposed over Tailscale ([web/README.md](web/README.md))
- **HDMI visualizer** — cava bars on a monitor, hotplug-aware, optional
  ([visualizer/README.md](visualizer/README.md))

## Hardware

- Raspberry Pi Zero 2 W (512 MB RAM)
- InnoMaker DAC Mini HAT (PCM5122) — or plain HDMI audio as a fallback
- DietPi Lite 64-bit (Bookworm), headless

## Setup from a clean DietPi

1. Flash DietPi and do the headless pre-boot config on the SD card:
   `dietpi-wifi.txt` (SSID + password), and in `dietpi.txt` set
   `AUTO_SETUP_SSH_SERVER_INDEX=-2` (OpenSSH). Boot, let DietPi finish its
   first-run update, log in over SSH.

2. Run the full setup:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/setup.sh | sudo bash
   ```

   Knobs (env vars, prepend to the command):

   | Env | Default | Meaning |
   |---|---|---|
   | `PISTREAM_AUDIO` | `dac` | `dac` = DAC HAT overlay, `hdmi` = on-board HDMI audio |
   | `PISTREAM_DAC_OVERLAY` | `allo-boss-dac-pcm512x-audio` | overlay for the DAC (alternative: `hifiberry-dacplus`) |
   | `PISTREAM_VISUALIZER` | `0` | `1` = also install the HDMI visualizer |
   | `PISTREAM_TAILSCALE` | `1` | `0` = skip Tailscale install |

   Example — HDMI audio + visualizer:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/setup.sh | sudo PISTREAM_AUDIO=hdmi PISTREAM_VISUALIZER=1 bash
   ```

3. Reboot when the script asks for it, then finish the manual steps it prints:
   - `tailscale up` (authorize via URL; disable key expiry for the machine in
     the Tailscale admin panel — it is headless)
   - LMS plugins at `http://<pi>:9000`: enable **TIDAL local** (disable the old
     TIDAL), **Material Skin**, optionally **Radio Browser**; restart LMS and
     authorize the TIDAL account
   - open the panel at `http://<pi>:8787` (language can be switched in `/settings`)

The script is idempotent — re-running it is safe and doubles as an update.

## Moving the device to a new location

The device only needs to get onto *some* network once — after that it is
reachable over Tailscale and everything else can be done from the panel.
The practical recipe:

1. **Before the move**, open `/settings` in the panel and manually add the
   Wi-Fi of the destination (SSID + password, works out of range) — and, as a
   fallback that works anywhere, **your phone's hotspot** as a saved network.
2. At the new place the device joins the known network (or your hotspot) on
   its own; reach the panel via Tailscale and add the local Wi-Fi from there.

The `/settings` page also shows the current **LAN IP / Tailscale IP** in case
MagicDNS is not resolving. A captive-portal fallback AP (Chromecast-style
first-run setup) is planned but not built yet.

## Repo layout

| Path | What it is |
|---|---|
| `setup.sh` | full provisioning of a clean DietPi (everything below included) |
| `web/` | control panel (Python stdlib microservice) + bt-agent, own `install.sh` |
| `visualizer/` | cava HDMI visualizer + audio tee, own `install.sh` / `uninstall.sh` |
| `plan.md` | original configuration plan / design notes |
| `dac-setup.md` | how to switch audio back from HDMI to a (working) DAC HAT |

## Notes

- No central audio server (PulseAudio/PipeWire): on a hardware DAC the first
  playing source owns the output, the rest get "device busy". Two mitigations:
  the panel auto-pauses the previous source when a new one starts ("new
  playback wins"), and squeezelite runs with `-C 5` so a paused LMS releases
  the DAC after 5 s.
- The panel has no authentication — expose it over **Tailscale**, never to the
  public internet.
- RAM budget (idle, approx.): DietPi ~70 + LMS ~150 + Squeezelite ~8 +
  shairport ~8 + bluealsa ~8 + tailscale ~30 ≈ ~280 MB → zram (installed by
  `setup.sh`) as the safety margin.
- **Naming**: the project used to be called *PiStream*; internal identifiers
  (systemd units `pistream-*`, `/opt/pistream-*` paths, `PISTREAM_*` env vars,
  the `pistream` ALSA device) keep the old name on purpose — renaming them
  would break updates on already-deployed devices. The display name in the
  panel comes from the device hostname (override with `PISTREAM_NAME`).
