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

GLSL_BIN="$(command -v glslViewer || command -v glslviewer || true)"
if [[ $ENGINE == glsl && -n $GLSL_BIN && -f $DIR/glsl/$SHADER.frag ]]; then
  exec bash -c "python3 '$DIR/glsl-audio-bridge.py' | '$GLSL_BIN' '$DIR/glsl/$SHADER.frag' --fullscreen"
fi
exec /usr/bin/cava -p "$DIR/cava.conf"
