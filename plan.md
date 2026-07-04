# Synchrofazotron — configuration plan (design notes)

> Historical planning document. The actual provisioning is automated by
> `setup.sh` (see the main README); this file keeps the reasoning and the
> decisions.

## Hardware
- Raspberry Pi Zero 2 W (512 MB RAM)
- InnoMaker DAC Mini HAT (PCM5122)
- Hammer header (press-fit)

## Hardware status (historical)
- The original DAC was not detected: `i2cdetect -y 1` empty (no `4d`), red LED
  went dark. Later confirmed dead (see `dac-setup.md`) — most likely ESD/short.
- Pi power was fine (`vcgencmd get_throttled` = 0x0), so cable/PSU not guilty.
- NOTE: never mount the HAT at an angle — risk of shorting adjacent pins.

## OS
- DietPi Lite 64-bit (Bookworm), headless
- Headless pre-boot config: `dietpi-wifi.txt` (SSID+password),
  `dietpi.txt` → `AUTO_SETUP_SSH_SERVER_INDEX=-2`

## DAC driver (overlay)
- Per the InnoMaker manual: `dtoverlay=allo-boss-dac-pcm512x-audio`
  (NOT hifiberry — that was a wrong attempt; the card shows up as "BossDAC")
- Set in: `dietpi-config → Audio Options → Sound card → allo-boss-dac-pcm512x-audio`
  (or `setup.sh` does it non-interactively)
- Verification: `aplay -l` (BossDAC card), `alsamixer` (Digital control), `speaker-test`

## RAM / stability
- zram: `apt install zram-tools`, in `/etc/default/zramswap` → `ALGO=zstd`, `PERCENT=50`
- Leave the default (small) swap alone

## Architecture: OPTION A (everything on the Pi, self-contained)
- LMS (Lyrion Music Server = the "brain") + Squeezelite (player) — both on the Pi

## To install
- **LMS + Squeezelite**: `dietpi-software install 35 36`
- **Shairport-Sync** (AirPlay) — via `dietpi-software` (id 37)
- **Avahi-Daemon** (discovery, required for AirPlay + LMS) — `dietpi-software` (id 152)
- **Tailscale** — `dietpi-software` or `curl -fsSL https://tailscale.com/install.sh | sh`
- **Spotify Connect (raspotify)**: `curl -sL https://dtcooper.github.io/raspotify/install.sh | sh`
- **Bluetooth A2DP** (bluez + bluealsa) — manual configuration (see below)

## LMS configuration (http://<pi-ip>:9000)
- Settings → Manage Plugins:
  - enable **TIDAL local**, disable the old **TIDAL**
  - enable **Material Skin**
  - (optionally) **Radio Browser** for internet radio
- Restart, then Settings → Advanced → TIDAL → authorize the account
- Squeezelite: point the `-o` output at the DAC card (`/etc/default/squeezelite`)

## Bluetooth A2DP (the "fiddly" step)
- Enable the adapter: `dietpi-config → Bluetooth`
- `apt install bluez-alsa-utils`
- Pairing:
  bluetoothctl
  power on
  agent on
  default-agent
  scan on
  pair <MAC>
  trust <MAC>    # trust = auto-reconnect
  connect <MAC>
- Point the bluealsa output at the DAC card

(These manual steps are now covered by the web panel + bt-agent from `web/`.)

## Tailscale
- `tailscale up`, authorize via URL
- In the admin panel: disable key expiry for this machine (headless)

## Control apps (phone)
- Tidal + radio: **Squeezer** (Android) / **iPeng** (iOS) or Material web (:9000)
- Spotify: the native Spotify app
- AirPlay: native
- YouTube Music / the rest: via Bluetooth

## Deliberately skipped
- Roon Bridge — no
- Snapcast (multi-room) — no
- FCast — postponed (receiver is GUI/Electron only, too heavy for a headless
  512 MB box; test with Grayjay on a laptop/Android)
- Docker / native Tidal Connect — no (too heavy for 512 MB; TIDAL local in LMS instead)
- Library server on the Pi (Navidrome/Jellyfin) — no (files live on a remote
  server in the tailnet; played to the Pi over Bluetooth from the phone app)

## Notes from the InnoMaker manual
- Disable the Wi-Fi hotspot; the RCA/3.5mm jacks pick up Wi-Fi interference
  (relevant with the shared radio on the Zero 2 W — keep in mind when tuning BT/Wi-Fi)

## RAM budget (option A, rough idle numbers)
- DietPi ~70 + LMS ~150 + Squeezelite ~8 + raspotify ~20 + shairport ~8
  + bluealsa ~8 + tailscale ~30 ≈ ~290 MB → zram as the safety margin
