#!/bin/bash
# Engine dispatcher for pistream-visualizer.service. /opt/pistream-visualizer/engine
# (written by the panel) selects what runs on the HDMI console:
#   cava            -> cava bars (default)
#   glsl <shader>   -> glsl-audio-bridge | viz-glsl glsl/<shader>.frag
# viz-glsl is our own minimal DRM/GLES2 runner (visualizer/viz-glsl.c) —
# glslViewer is kept only as a fallback (its vera backend never actually
# displayed anything on VC4 despite rendering; see repo history 2026-07-07).
# Falls back to cava whenever no runner or shader is present, so a bad
# switch never leaves a black screen.
set -u

DIR=/opt/pistream-visualizer
ENGINE=cava SHADER=plasma
[[ -r $DIR/engine ]] && read -r ENGINE SHADER < "$DIR/engine" || true
[[ -n ${SHADER:-} ]] || SHADER=plasma

# On any bail-out the reason lands in $DIR/glsl-error — the panel shows it
# (a silent fallback to cava looks like "the feature just doesn't work").
GLSL_BIN="$(command -v viz-glsl || command -v glslViewer || command -v glslviewer || true)"
if [[ $ENGINE == glsl ]]; then
  if [[ ! -f $DIR/glsl/$SHADER.frag ]]; then
    echo "shader '$SHADER' not found in $DIR/glsl" > "$DIR/glsl-error"
  elif [[ -n $GLSL_BIN ]]; then
    rm -f "$DIR/glsl-error"
    # viz-glsl takes just the shader path; glslViewer needs its flags
    # (--noncurses because the service has no TERM for the ncurses console)
    ARGS=""
    [[ $GLSL_BIN == *glslViewer || $GLSL_BIN == *glslviewer ]] && \
      ARGS="--fullscreen --noncurses --nocursor"
    # no exec: if the binary dies right away (e.g. DRM init failure), fall
    # back to cava instead of letting systemd crash-loop a black screen
    START=$SECONDS
    bash -c "python3 '$DIR/glsl-audio-bridge.py' | '$GLSL_BIN' '$DIR/glsl/$SHADER.frag' $ARGS"
    RC=$?
    if (( SECONDS - START < 10 )); then
      echo "$(basename "$GLSL_BIN") exited immediately (rc=$RC) — details: journalctl -u pistream-visualizer" > "$DIR/glsl-error"
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
