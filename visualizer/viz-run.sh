#!/bin/bash
# Engine dispatcher for pistream-visualizer.service. /opt/pistream-visualizer/engine
# (written by the panel) selects what runs on the HDMI console:
#   cava            -> cava bars (default)
#   glsl <shader>   -> glsl-audio-bridge | glslViewer glsl/<shader>.frag
# Falls back to cava whenever glslViewer or the shader is missing, so a bad
# switch never leaves a black screen.
set -u

DIR=/opt/pistream-visualizer
ENGINE=cava SHADER=plasma
[[ -r $DIR/engine ]] && read -r ENGINE SHADER < "$DIR/engine" || true
[[ -n ${SHADER:-} ]] || SHADER=plasma

# On any bail-out the reason lands in $DIR/glsl-error — the panel shows it
# (a silent fallback to cava looks like "the feature just doesn't work").
GLSL_BIN="$(command -v glslViewer || command -v glslviewer || true)"
if [[ $ENGINE == glsl ]]; then
  if [[ ! -f $DIR/glsl/$SHADER.frag ]]; then
    echo "shader '$SHADER' not found in $DIR/glsl" > "$DIR/glsl-error"
  elif [[ -n $GLSL_BIN ]]; then
    rm -f "$DIR/glsl-error"
    # no exec: if the binary dies right away (e.g. DRM init failure), fall
    # back to cava instead of letting systemd crash-loop a black screen
    START=$SECONDS
    # --noncurses: the service has no TERM, so the ncurses console cannot
    # start anyway and only spews escape codes into the journal
    bash -c "python3 '$DIR/glsl-audio-bridge.py' | '$GLSL_BIN' '$DIR/glsl/$SHADER.frag' --fullscreen --noncurses --nocursor"
    RC=$?
    if (( SECONDS - START < 10 )); then
      echo "glslViewer exited immediately (rc=$RC) — details: journalctl -u pistream-visualizer" > "$DIR/glsl-error"
      exec /usr/bin/cava -p "$DIR/cava.conf"
    fi
    exit "$RC"
  elif python3 -c 'import pygame, OpenGL, numpy' 2>/dev/null; then
    # no glslViewer binary -> pygame/PyOpenGL runner (manages glsl-error itself)
    exec python3 "$DIR/glsl-run.py" "$DIR/glsl/$SHADER.frag"
  else
    echo "python GL stack missing (python3-pygame / python3-opengl / python3-numpy)" > "$DIR/glsl-error"
  fi
fi
exec /usr/bin/cava -p "$DIR/cava.conf"
