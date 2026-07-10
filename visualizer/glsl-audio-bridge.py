#!/usr/bin/env python3
"""Audio -> glslViewer uniform bridge.

Reads the stream copy from the snd-aloop loopback (the same tap cava uses),
computes level + three FFT bands and prints them as glslViewer console
commands on stdout at ~43 Hz:

    u_level,0.4213
    u_bass,0.8120
    ...

Wire it up with a pipe (viz-run.sh does):  glsl-audio-bridge.py | glslViewer x.frag

Values are 0..1 with fast attack / slow decay, so the shaders look snappy
without flickering. When nothing plays, the loopback capture blocks and the
picture simply freezes on the last frame — that is fine.
"""
import json
import subprocess
import sys

import numpy as np

# "Customize visualizer normalization" (panel: Config -> Experimental). The
# panel stores JSON: {"custom": bool, "glsl": {"max_boost", "target"}, ...}.
# Missing file, custom off, or legacy "0"/"1" content (the old on/off toggle)
# all mean the shipped AGC defaults below. The service restarts on every
# change, so reading once at startup is enough.
NORMALIZE_FILE = "/opt/pistream-visualizer/normalize"

RATE = 44100
CHUNK = 1024                      # 1024 frames @ 44.1 kHz -> ~43 updates/s
DEVICE = "plughw:Loopback,1,0"
BANDS = ((20, 250), (250, 2000), (2000, 8000))   # bass / mid / treble, Hz
GAINS = (3.0, 40.0, 60.0, 120.0)                 # level + per-band make-up gain
NAMES = ("u_level", "u_bass", "u_mid", "u_treble")
DECAY = 0.85
# AGC: the players apply software volume (squeezelite -W / LMS) BEFORE the
# tee, so the loopback copy is as quiet as the speakers — at LMS volume ~25
# the raw peak is under 0.01 and fixed gains starve the shaders (cava gets
# away with it thanks to autosens). Normalize by a running peak of the gained
# level: quiet playback is boosted up to AGC_MAX_BOOST, loud playback is
# gently normalized toward AGC_TARGET.
AGC_TARGET = 0.9
AGC_MAX_BOOST = 45.0
AGC_DECAY = 0.999                 # per chunk (~43 Hz): env halves in ~16 s


def _agc_params():
    """(max_boost, target) — the user's values when customization is on,
    the shipped defaults otherwise. max_boost 1.0 ~= raw (no boost, loud
    playback still capped toward target)."""
    try:
        with open(NORMALIZE_FILE, encoding="utf-8") as fh:
            cfg = json.load(fh)
        if isinstance(cfg, dict) and cfg.get("custom"):
            glsl = cfg.get("glsl") or {}
            boost = float(glsl.get("max_boost", AGC_MAX_BOOST))
            target = float(glsl.get("target", AGC_TARGET))
            return min(max(boost, 1.0), 100.0), min(max(target, 0.1), 1.0)
    except (OSError, ValueError, TypeError):
        pass
    return AGC_MAX_BOOST, AGC_TARGET


def main():
    rec = subprocess.Popen(
        ["arecord", "-q", "-D", DEVICE, "-f", "S16_LE",
         "-r", str(RATE), "-c", "2", "-t", "raw"],
        stdout=subprocess.PIPE)
    window = np.hanning(CHUNK)
    freqs = np.fft.rfftfreq(CHUNK, 1.0 / RATE)
    masks = [(freqs >= lo) & (freqs < hi) for lo, hi in BANDS]
    state = [0.0] * len(NAMES)
    env = 0.0                     # running peak of the gained level (AGC)
    max_boost, target = _agc_params()
    while True:
        raw = rec.stdout.read(CHUNK * 4)          # 2 ch * 2 bytes
        if len(raw) < CHUNK * 4:
            break
        x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
        mono = (x[0::2] + x[1::2]) * 0.5
        spec = np.abs(np.fft.rfft(mono * window)) / CHUNK
        vals = [float(np.sqrt(np.mean(mono ** 2)))]
        vals += [float(np.sqrt(np.mean(spec[m] ** 2))) for m in masks]
        gained = [v * g for v, g in zip(vals, GAINS)]
        env = max(env * AGC_DECAY, gained[0])
        scale = target / max(env, target / max_boost)
        lines = []
        for i, v in enumerate(gained):
            v = min(v * scale, 1.0)
            state[i] = v if v > state[i] else state[i] * DECAY + v * (1 - DECAY)
            lines.append(f"{NAMES[i]},{state[i]:.4f}")
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
