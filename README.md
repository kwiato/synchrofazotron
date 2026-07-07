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
   | `PISTREAM_AP_FALLBACK` | `1` | `0` = skip the setup-AP fallback (captive portal) |

   Example — HDMI audio + visualizer:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/setup.sh | sudo PISTREAM_AUDIO=hdmi PISTREAM_VISUALIZER=1 bash
   ```

3. Reboot when the script asks for it, then finish the manual steps it prints:
   - `tailscale up` (authorize via URL; disable key expiry for the machine in
     the Tailscale admin panel — it is headless)
   - authorize the TIDAL account at `http://<pi>:9000` → Settings → Advanced →
     TIDAL (**Material Skin** and **TIDAL local** are installed automatically,
     analytics reporting is disabled; optional plugin: **Radio Browser**)
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
MagicDNS is not resolving.

And if none of that was prepared: after ~2 minutes without Wi-Fi the device
raises its own **setup AP** (`Synchrofazotron-Setup`, password
`synchrofazotron`) with a captive portal that opens the panel — add the local
network there and the device switches over on its own. Details in
[ap-fallback/README.md](ap-fallback/README.md).

## Visualizer

With a monitor plugged into the Pi's HDMI port, Synchrofazotron turns into a
music visualizer: an HDMI hotplug watcher starts the show automatically when
the cable goes in and stops it when it goes out — the music itself is never
interrupted. Two engines are available, switchable from the panel's
`/settings` page:

- **cava** — classic spectrum bars on the console (default)
- **GLSL shaders** — audio-reactive fragment shaders (plasma, tunnel, copper,
  cube, oscilloscope, grid…)
  rendered by viz-glsl, our minimal DRM/GLES2 runner, fed with levels
  (`u_level`, `u_bass`, `u_mid`, `u_treble`) by a small audio bridge

Install with `PISTREAM_VISUALIZER=1` during setup, or later with
`visualizer/install.sh`. Details in [visualizer/README.md](visualizer/README.md).

### Editing the visualizations

- **Shader studio** — open `visualizer/visualizer-studio.html` in a browser
  (works straight from `file://`). It is a live-recompiling GLSL editor with
  the repo presets, browser-saved drafts, `.frag` upload ("Load .frag"),
  Mesa-style error lines, emulated bridge uniforms (fake beat / microphone /
  sliders) and `.frag` export. WebGL 1
  compiles the same GLSL ES 1.00 dialect as the Pi's VC4 GPU, so what compiles
  in the studio compiles on the device. To preview the current `glsl/*.frag`
  files serve the repo first (`python -m http.server`), or use "Watch .frag"
  (Chrome/Edge) to edit in your own editor and recompile on every save.
- **Panel** — `http://<pi>:8787/settings` lets you switch engines, edit the
  cava color presets and upload `.frag` files exported from the studio
  (drag & drop) directly to the device.

## Repo layout

| Path | What it is |
|---|---|
| `setup.sh` | full provisioning of a clean DietPi (everything below included) |
| `web/` | control panel (Python stdlib microservice) + bt-agent, own `install.sh`; UI preview on any machine: `python web/pistream_panel.py` → `http://127.0.0.1:8787` (details in `web/README.md`) |
| `ap-fallback/` | setup AP + captive portal when Wi-Fi is down, own `install.sh` / `uninstall.sh` |
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

## TODO

- Test and fix HDMI audio output (the panel's DAC ↔ HDMI switch rewrites the
  boot config, but the HDMI path has not been verified end-to-end on unit #2).
- BLE provisioning (Improv Wi-Fi) as part of the companion app — see plan.md.
- Test the AP-fallback captive portal on real hardware (`ifdown wlan0`, watch
  `journalctl -fu pistream-net-watch`).
- Promote the `glyphs` shader draft from the studio to `visualizer/glsl/`
  once it looks right.

## Credits

Synchrofazotron is a thin layer of glue — the heavy lifting is done by these
excellent open-source projects and the people behind them:

| Project | Author / community | What it does here |
|---|---|---|
| [cava](https://github.com/karlstav/cava) | [Karl Stavestrand](https://github.com/karlstav) | console audio spectrum — the bars engine |
| [glslViewer](https://github.com/patriciogonzalezvivo/glslViewer) | [Patricio Gonzalez Vivo](https://github.com/patriciogonzalezvivo) | GLSL shader engine (demoscene presets) |
| [Lyrion Music Server](https://github.com/LMS-Community/slimserver) | [LMS Community](https://github.com/LMS-Community) | music server: TIDAL, radio, local library |
| [Material Skin](https://github.com/CDrummond/lms-material) | [Craig Drummond](https://github.com/CDrummond) | the LMS web UI actually worth using |
| [squeezelite](https://github.com/ralph-irving/squeezelite) | Adrian Smith, [Ralph Irving](https://github.com/ralph-irving) | the LMS player endpoint |
| [Shairport Sync](https://github.com/mikebrady/shairport-sync) | [Mike Brady](https://github.com/mikebrady) | AirPlay receiver |
| [BlueALSA](https://github.com/arkq/bluez-alsa) | [Arkadiusz Bokowy](https://github.com/arkq) | Bluetooth A2DP sink without PulseAudio |
| [bluez-tools](https://github.com/khvzak/bluez-tools) | [Alexander Orlenko](https://github.com/khvzak) | headless BT pairing agent |
| [DietPi](https://github.com/MichaIng/DietPi) | [MichaIng](https://github.com/MichaIng) & community | the lightweight OS underneath it all |
| [Tailscale](https://github.com/tailscale/tailscale) | Tailscale Inc. | zero-config remote access |
| [NumPy](https://github.com/numpy/numpy) | NumPy developers | FFT for the audio→shader bridge |
| [Slimshader](https://github.com/ErikOostveen/Slimshader) | [Erik Oostveen](https://github.com/ErikOostveen) | inspiration for audio-reactive shaders on a Pi |
