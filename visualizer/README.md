# Synchrofazotron visualizer — cava bars on HDMI

"Fireworks for special occasions": when an HDMI display is plugged into the Pi,
[cava](https://github.com/karlstav/cava) bars dance on the screen in sync with
whatever is playing (LMS, AirPlay, Bluetooth). With HDMI unplugged the
visualizer is off and uses no resources. Music plays identically either way.

## Architecture

```
sources (squeezelite / shairport / bluealsa-aplay)
   └─> pcm "pistream"  (ALSA: plug -> route -> multi)
         ├─> hw:BossDAC          (audio — always)
         └─> hw:Loopback,0,0     (stream copy — snd-aloop)
                └─> plughw:Loopback,1,0  <- read by cava (only when HDMI is in)
```

- **The audio path is fixed** — plugging HDMI in only decides whether cava
  runs. That way plugging/unplugging the cable never interrupts the music.
  (Re-routing the path dynamically would require restarting the players on
  every hotplug, because libasound reads its configuration once per process.)
- **`pistream-hdmi-watch`** checks `/sys/class/drm/*-HDMI-*/status` every 5 s
  and starts/stops `pistream-visualizer` (cava on `tty1`).
- Fixed cost: negligible CPU for copying samples; the path goes through `plug`,
  so it formally stops being bit-perfect (inaudible in practice).

## GLSL presets & preview harness

`glsl/*.frag` are audio-reactive fragment shaders run on the Pi by glslViewer
(fed by `glsl-audio-bridge.py`: `u_level`, `u_bass`, `u_mid`, `u_treble`).
To iterate on shaders without the Pi, open **`preview.html`** in a browser —
WebGL 1 compiles the same GLSL ES 1.00 dialect the Pi's VC4 GPU enforces, so
what compiles there compiles here. It emulates the bridge uniforms (fake beat
/ microphone / sliders) and, in Chrome/Edge, recompiles a watched `.frag` on
every save. Serve the repo (`python -m http.server`) to get the preset
buttons, or just drag & drop a shader file onto the page.

## Install / update

```bash
curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/visualizer/install.sh | sudo bash
```

The script backs up every config it touches (`*.bak.<date>`). Full revert to
the direct audio path:

```bash
curl -fsSL https://raw.githubusercontent.com/kwiato/synchrofazotron/main/visualizer/uninstall.sh | sudo bash
```

## Manual control

```bash
systemctl start|stop pistream-visualizer     # manual fireworks
systemctl stop pistream-hdmi-watch           # disable the automation (until reboot)
# login console on HDMI instead of the visualizer:
systemctl stop pistream-hdmi-watch pistream-visualizer && systemctl start getty@tty1
```

The visualizer occupies `tty1`; text consoles remain available on Alt+F2…F6.

## Troubleshooting

- **Bars frozen despite music playing** — check that the source really plays
  through `pistream`: `grep -E 'SL_SOUNDCARD|-o ' /etc/default/squeezelite`
  (and the same for shairport/bluealsa). Sources need a restart after install
  (the script does that).
- **Loopback test without HDMI**: play some music and run
  `arecord -D plughw:Loopback,1,0 -f S16_LE -d 1 /tmp/t.wav` — the file should
  contain sound, not silence.
- **The watcher exits immediately** — a kernel without KMS exposes no DRM
  status; manual control remains (see above).
- **cava looks washed out** — the Linux console has a poor palette;
  colors/gradients can be tuned in `/opt/pistream-visualizer/cava.conf`
  (`[color]` section), then `systemctl restart pistream-visualizer`.
  Presets are also available in the panel under `/settings`.

## Files

| File | Goes to | Role |
|---|---|---|
| `asound-tee.conf` | block in `/etc/asound.conf` | the `pistream` device (DAC+loopback) |
| `cava.conf` | `/opt/pistream-visualizer/` | visualizer configuration |
| `hdmi-watch.sh` | `/opt/pistream-visualizer/` | HDMI hotplug loop |
| `pistream-visualizer.service` | `/etc/systemd/system/` | cava on tty1 |
| `pistream-hdmi-watch.service` | `/etc/systemd/system/` | watcher (enabled) |
