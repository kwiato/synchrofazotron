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
import subprocess
import sys

import numpy as np

RATE = 44100
CHUNK = 1024                      # 1024 frames @ 44.1 kHz -> ~43 updates/s
DEVICE = "plughw:Loopback,1,0"
BANDS = ((20, 250), (250, 2000), (2000, 8000))   # bass / mid / treble, Hz
GAINS = (3.0, 40.0, 60.0, 120.0)                 # level + per-band make-up gain
NAMES = ("u_level", "u_bass", "u_mid", "u_treble")
DECAY = 0.85


def main():
    rec = subprocess.Popen(
        ["arecord", "-q", "-D", DEVICE, "-f", "S16_LE",
         "-r", str(RATE), "-c", "2", "-t", "raw"],
        stdout=subprocess.PIPE)
    window = np.hanning(CHUNK)
    freqs = np.fft.rfftfreq(CHUNK, 1.0 / RATE)
    masks = [(freqs >= lo) & (freqs < hi) for lo, hi in BANDS]
    state = [0.0] * len(NAMES)
    while True:
        raw = rec.stdout.read(CHUNK * 4)          # 2 ch * 2 bytes
        if len(raw) < CHUNK * 4:
            break
        x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
        mono = (x[0::2] + x[1::2]) * 0.5
        spec = np.abs(np.fft.rfft(mono * window)) / CHUNK
        vals = [float(np.sqrt(np.mean(mono ** 2)))]
        vals += [float(np.sqrt(np.mean(spec[m] ** 2))) for m in masks]
        lines = []
        for i, v in enumerate(vals):
            v = min(v * GAINS[i], 1.0)
            state[i] = v if v > state[i] else state[i] * DECAY + v * (1 - DECAY)
            lines.append(f"{NAMES[i]},{state[i]:.4f}")
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
