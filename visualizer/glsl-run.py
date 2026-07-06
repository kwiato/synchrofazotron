#!/usr/bin/env python3
"""Fallback GLSL engine — used when the glslViewer binary is unavailable
(there is no arm64 APT package). pygame (SDL2 KMSDRM — straight to the
console, no X) + PyOpenGL draw a fullscreen fragment shader; a background
thread feeds the same audio uniforms the glslViewer path gets from
glsl-audio-bridge.py (u_level/u_bass/u_mid/u_treble, 0..1, fast attack /
slow decay).

Usage: glsl-run.py /opt/pistream-visualizer/glsl/plasma.frag

If video/GL init or the shader compile fails, it execs cava instead, so the
visualizer service never ends up in a black-screen restart loop.
"""
import os
import subprocess
import sys
import threading
import time

import numpy as np

VIZ_DIR = "/opt/pistream-visualizer"
RATE, CHUNK = 44100, 1024
DEVICE = "plughw:Loopback,1,0"
BANDS = ((20, 250), (250, 2000), (2000, 8000))   # bass / mid / treble, Hz
GAINS = (3.0, 40.0, 60.0, 120.0)                 # level + per-band make-up gain
DECAY = 0.85
FPS = 45

VERT = "attribute vec2 a_pos; void main() { gl_Position = vec4(a_pos, 0.0, 1.0); }"


ERR_FILE = f"{VIZ_DIR}/glsl-error"


def fallback_to_cava(reason):
    # leave the reason where the panel can show it (never hide a failure)
    try:
        with open(ERR_FILE, "w", encoding="utf-8") as fh:
            fh.write(reason + "\n")
    except OSError:
        pass
    sys.stderr.write(f"glsl-run: {reason} — falling back to cava\n")
    sys.stderr.flush()
    os.execv("/usr/bin/cava", ["cava", "-p", f"{VIZ_DIR}/cava.conf"])


class AudioBands(threading.Thread):
    """arecord from the loopback -> FFT -> smoothed values in self.state."""

    def __init__(self):
        super().__init__(daemon=True)
        self.state = [0.0, 0.0, 0.0, 0.0]

    def run(self):
        window = np.hanning(CHUNK)
        freqs = np.fft.rfftfreq(CHUNK, 1.0 / RATE)
        masks = [(freqs >= lo) & (freqs < hi) for lo, hi in BANDS]
        while True:
            rec = subprocess.Popen(
                ["arecord", "-q", "-D", DEVICE, "-f", "S16_LE",
                 "-r", str(RATE), "-c", "2", "-t", "raw"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            while True:
                raw = rec.stdout.read(CHUNK * 4)          # 2 ch * 2 bytes
                if len(raw) < CHUNK * 4:
                    break
                x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
                mono = (x[0::2] + x[1::2]) * 0.5
                spec = np.abs(np.fft.rfft(mono * window)) / CHUNK
                vals = [float(np.sqrt(np.mean(mono ** 2)))]
                vals += [float(np.sqrt(np.mean(spec[m] ** 2))) for m in masks]
                for i, v in enumerate(vals):
                    v = min(v * GAINS[i], 1.0)
                    self.state[i] = v if v > self.state[i] else \
                        self.state[i] * DECAY + v * (1 - DECAY)
            rec.wait()
            time.sleep(1)   # loopback busy or gone — retry

def main():
    try:
        os.remove(ERR_FILE)   # fresh attempt — clear the previous verdict
    except OSError:
        pass
    if len(sys.argv) != 2 or not os.path.isfile(sys.argv[1]):
        fallback_to_cava("shader argument missing")
    frag = open(sys.argv[1], encoding="utf-8").read()

    # Without X, PyOpenGL must resolve GL through EGL (its default is GLX,
    # which explodes on the first GL call on a console-only system).
    os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")  # no tty banner
    try:
        import pygame
        from OpenGL import GL
    except Exception as e:  # noqa: BLE001
        fallback_to_cava(f"python GL stack missing ({e})")

    # vc4/KMSDRM is happiest with a GLES2 context (the RetroPie-trodden
    # path); plain desktop GL is the second attempt.
    def try_set_mode(es2):
        pygame.display.quit()
        pygame.display.init()
        if es2:
            pygame.display.gl_set_attribute(
                pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_ES)
            pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 2)
            pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 0)
        pygame.display.set_mode((0, 0),
                                pygame.FULLSCREEN | pygame.OPENGL | pygame.DOUBLEBUF)

    err = None
    for es2 in (True, False):
        try:
            try_set_mode(es2)
            err = None
            break
        except Exception as e:  # noqa: BLE001
            err = e
    if err is not None:
        fallback_to_cava(f"video init failed ({err})")
    pygame.mouse.set_visible(False)
    width, height = pygame.display.get_window_size()

    def compile_shader(src, kind):
        s = GL.glCreateShader(kind)
        GL.glShaderSource(s, src)
        GL.glCompileShader(s)
        if not GL.glGetShaderiv(s, GL.GL_COMPILE_STATUS):
            raise RuntimeError(GL.glGetShaderInfoLog(s))
        return s

    try:
        prog = GL.glCreateProgram()
        GL.glAttachShader(prog, compile_shader(VERT, GL.GL_VERTEX_SHADER))
        GL.glAttachShader(prog, compile_shader(frag, GL.GL_FRAGMENT_SHADER))
        GL.glBindAttribLocation(prog, 0, "a_pos")
        GL.glLinkProgram(prog)
        if not GL.glGetProgramiv(prog, GL.GL_LINK_STATUS):
            raise RuntimeError(GL.glGetProgramInfoLog(prog))
    except Exception as e:  # noqa: BLE001
        fallback_to_cava(f"shader compile failed ({e})")

    GL.glUseProgram(prog)
    GL.glViewport(0, 0, width, height)
    # one big triangle covering the screen — no index buffers needed
    quad = np.array([-1, -1, 3, -1, -1, 3], dtype=np.float32)
    GL.glEnableVertexAttribArray(0)
    GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, GL.GL_FALSE, 0, quad)
    loc = {n: GL.glGetUniformLocation(prog, n) for n in
           ("u_time", "u_resolution", "u_level", "u_bass", "u_mid", "u_treble")}
    if loc["u_resolution"] != -1:
        GL.glUniform2f(loc["u_resolution"], float(width), float(height))

    audio = AudioBands()
    audio.start()
    clock = pygame.time.Clock()
    t0 = time.monotonic()
    names = ("u_level", "u_bass", "u_mid", "u_treble")
    while True:
        pygame.event.pump()
        if loc["u_time"] != -1:
            GL.glUniform1f(loc["u_time"], time.monotonic() - t0)
        for i, name in enumerate(names):
            if loc[name] != -1:
                GL.glUniform1f(loc[name], audio.state[i])
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
