# Synchrofazotron — restoring audio through the DAC (to do once a working DAC arrives)

> Status as of 2026-07-01: the original InnoMaker DAC Mini HAT (PCM5122) is
> **dead** (no response on I2C `0x4d` on two different Pis, LED dark — most
> likely ESD/short from a touch). As a workaround Synchrofazotron currently plays
> through **HDMI audio** (the monitor's jack). This file describes how to go
> back to the DAC once a working unit is in hand.
>
> Note: on a fresh device `setup.sh` handles both variants
> (`PISTREAM_AUDIO=dac|hdmi`). This file remains useful for switching an
> already-configured device from HDMI back to a DAC.

## 0. Hardware swap
- Mount the working DAC HAT (flat, hammer header pressed evenly, never at an angle).
- Sanity-check before touching software:
  ```bash
  i2cdetect -y 1        # the PCM5122 should show up as 4d (or UU if the driver claimed it)
  ```
  If `4d`/`UU` does NOT appear — it is still hardware/contact, leave the config alone.

## 1. config.txt — switch audio from HDMI to the DAC
File: `/boot/firmware/config.txt` (backups of the 2026-07-01 changes sit next
to it as `*.bak.*`).

Disable the on-board audio and enable the DAC overlay:
```ini
dtparam=audio=off            # was: on (for HDMI); the DAC requires off
#hdmi_drive=2                 # unnecessary for the DAC (can stay, does no harm)
#hdmi_force_hotplug=1         # same
dtoverlay=hifiberry-dacplus   # see the overlay note below
```

### ⚠️ Which overlay — to be confirmed on a live DAC
- The plan (`plan.md`) per the InnoMaker manual: `dtoverlay=allo-boss-dac-pcm512x-audio`
  ("BossDAC" card).
- An earlier `hifiberry-dacplus` attempt did not wake the chip either — BUT both
  cases failed only with `-121` (chip not responding = dead hardware), so this
  does **not** settle which overlay is correct. The
  `snd_soc_register_card ... -517` errors with allo-boss are EPROBE_DEFER
  (normal), not a sign of a wrong overlay.
- **Test both on a working DAC** and keep the one where: `aplay -l` shows the
  card, `dmesg | grep pcm512` has no `-121`, and the LED is lit.
  Order of attempts: `allo-boss-dac-pcm512x-audio` first (per the manual),
  if that fails → `hifiberry-dacplus`.

## 2. Revert the HDMI-audio workaround (DietPi blacklists the on-board audio, which suits the DAC)
With the DAC, the on-board `snd_bcm2835` is not needed. Restore the blacklist:
```bash
# restore the original (there was a backup):
mv /etc/modprobe.d/dietpi-disable_rpi_audio.conf.bak.* /etc/modprobe.d/dietpi-disable_rpi_audio.conf  # if you want 1:1
# or manually un-comment: blacklist snd_bcm2835
rm -f /etc/modules-load.d/hdmi-audio.conf       # remove the forced HDMI audio module load
```
Update `/etc/asound.conf` (default card 0) to the DAC card after checking its
number in `aplay -l` (it will usually also be card 0 once HDMI audio is off —
confirm).

## 3. Reboot and verify
```bash
reboot
# after the restart:
aplay -l                      # expected: the DAC card (BossDAC / sndrpihifiberry)
alsamixer                     # the Digital control — raise it, unmute
speaker-test -c2 -twav        # test on the DAC
```

## 4. Point the players at the DAC
- **Squeezelite**: `/etc/default/squeezelite` → the `-o` parameter to the DAC
  card (e.g. `SQUEEZELITE_OUTPUT_DEVICE=hw:CARD=sndrpihifiberry` — confirm the
  name with `aplay -l`), then `systemctl restart squeezelite`.
- **Shairport-Sync**: `/etc/shairport-sync.conf` → `alsa { output_device = "hw:0"; }` to the DAC card.
- **Raspotify**: `/etc/raspotify/conf` → `LIBRESPOT_DEVICE` to the DAC card.
- **bluealsa** (if BT): redirect the output to the DAC card.
- (If the visualizer is installed, the players target `pistream` instead —
  update `pistream_dac` in `/etc/asound.conf` rather than the players.)

## 5. Note from the InnoMaker manual
- Disable the Wi-Fi hotspot / weigh Wi-Fi against interference — the RCA/3.5mm
  jacks pick up Wi-Fi noise (relevant on the Zero 2 W's shared radio).

---
### Log of the changes made 2026-07-01 (the HDMI workaround — revert per the above)
- `config.txt`: `audio=off→on`, `hdmi_blanking=1→0`, added `hdmi_drive=2`,
  `hdmi_force_hotplug=1`, commented out `dtoverlay=hifiberry-dacplus`.
- `/etc/modprobe.d/dietpi-disable_rpi_audio.conf`: commented out `blacklist snd_bcm2835`.
- Added `/etc/modules-load.d/hdmi-audio.conf` (`snd_bcm2835`).
- Added `/etc/asound.conf` (default card 0 = bcm2835 HDMI).
