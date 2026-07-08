# Audio output roadmap

How audio routing works, what changed, and what is left to build/test.

## Background — the tee and why switching used to need a reboot

With the visualizer installed, every source (squeezelite / shairport-sync /
bluealsa-aplay) targets one virtual ALSA device, `pistream`, which **copies**
the stream:

```
sources → pcm.pistream (plug: format/rate)
          → pistream_tee (route 2ch → 4ch)
            → pistream_multi (multi: split into two 2ch slaves)
               ├─ slave a: pistream_dac   → hw:<audible card>   (what you hear)
               └─ slave b: pistream_loop  → hw:Loopback,0        (copy for the visualizer)
```

The visualizer (cava + the GLSL audio bridge) captures `plughw:Loopback,1,0`.

Historically the DAC↔HDMI switch rewrote `config.txt` device-tree overlays
(DAC overlay vs `dtparam=audio=on`) **and** blacklisted the other card, so the
two cards were mutually exclusive and switching needed a **reboot**.

### The clock-drift fact (why "both cards at once" clicks)

Each real card has its own crystal. Feeding two real cards simultaneously via
`multi` means two independent clocks; one drains its buffer slightly faster and
periodically under/overruns → a click every few minutes. Muting one card does
**not** help — a muted card still clocks/consumes samples. Only feeding **one**
real card at a time (plus the soft Loopback, which has no crystal) is
drift-free. True simultaneous DAC+HDMI audio is therefore a separate,
opt-in "may click" mode.

## Option A — live single-output switching (IMPLEMENTED)

Panel picks the audible output live; only one real card is fed at a time, so no
drift. Implemented in `web/pistream_panel.py`:

- `_cards_present()` / `_dac_card_id()` / `_hdmi_card_id()` — detect which
  output cards are actually up (from `/proc/asound/cards`), by **name** (card
  numbering is unstable once both exist).
- `_audio_state()` now returns `cards: {dac, hdmi}` and `output` (the currently
  selected sink, read from the tee), plus `reboot_required` = the selected
  card is not up yet.
- `_audio_set(mode)`:
  - target card **already present** → **live switch**: repoint the tee's
    audible slave + the players, restart them (~1 s blip), **no reboot**.
  - target card **absent** → the legacy `config.txt` + overlay path (reboot).
- `_audio_tee_reconcile()` (run at panel startup) — if the tee points at a card
  that is not present (e.g. a visualizer reinstall reset it to `BossDAC` on an
  HDMI-only box), repoint it at whatever card IS up. **Fixes the silence-after-
  reinstall regression.**
- Panel UI: green/red dots on the DAC / HDMI buttons show card availability.

### Still to do on-device for A to be fully reboot-free

1. **Enable both cards at boot** (where the hardware allows) so switching never
   needs a reboot. In `config.txt`: keep the DAC overlay **and**
   `dtparam=audio=on`, and do **not** blacklist `snd_bcm2835`. Verify with
   `aplay -l` that both cards appear. This belongs in `setup.sh` (audio step)
   once verified on a live board — it is intentionally NOT changed blindly here.
2. **Confirm the HDMI card id** on the target board (`vc4hdmi0`, `b1`,
   `Headphones`, …) — `_hdmi_card_id()` matches on `hdmi|bcm2835|headphone|vc4|
   b1`; extend the pattern if a board reports something else.

## Option B — seamless bridge switching (TO TEST)

Goal: switch output with **no player restart / no blip**. Add per-detail below.

Sketch:
- Players always target a fixed sink (the tee), which copies to **two** Loopback
  substreams: one for the visualizer, one for a persistent **bridge** service.
- A small always-on bridge (à la `bluealsa-aplay`) reads the second Loopback
  capture and writes to the currently-selected real card. Switching output =
  restart only the bridge (players keep playing into the Loopback uninterrupted).
- Because only the bridge touches a real card, still only one crystal in play →
  drift-free.

Open questions to test:
- snd-aloop substream layout: the viz reads `Loopback,1,0`; the bridge would
  read `Loopback,1,1` fed from `Loopback,0,1` — needs the tee to fan out to
  **both** `Loopback,0,0` and `Loopback,0,1` (a 6-channel multi:
  DAC-or-none + loop0 + loop1). Verify aloop `pcm_substreams` and channel
  mapping.
- Bridge implementation: reuse `alsaloop` (from `alsa-utils`) or `bluealsa-aplay`
  style `aplay Loopback,1,1 | ... hw:<card>`; measure latency and CPU.
- Switch command: a tiny unit `pistream-bridge@<card>.service` the panel
  `try-restart`s with a different card token; persist the choice to a file.

## True simultaneous DAC + HDMI (opt-in, "may click")

A separate mode where the tee fans out to DAC **and** HDMI **and** Loopback
(6ch multi, each real card via its own `plug`). Drift-corrected properly only
by PipeWire/PulseAudio combine-sink (adaptive resampling) — which this project
deliberately avoids (RAM + DAC exclusivity). Offer as an explicit toggle with a
"may click" warning; default stays single-output switching.
