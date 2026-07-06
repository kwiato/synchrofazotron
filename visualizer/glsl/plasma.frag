// Synchrofazotron glsl preset: plasma — classic demoscene sine plasma.
// Audio uniforms come from glsl-audio-bridge.py (0..1, fast attack/slow decay).
#ifdef GL_ES
precision mediump float;
#endif

uniform vec2 u_resolution;
uniform float u_time;
uniform float u_level;
uniform float u_bass;
uniform float u_mid;
uniform float u_treble;

void main() {
    vec2 p = (2.0 * gl_FragCoord.xy - u_resolution) / min(u_resolution.x, u_resolution.y);
    float t = u_time * 0.7 + u_bass * 3.0;
    float v = sin(p.x * 3.0 + t)
            + sin(p.y * 4.0 - t * 1.3)
            + sin((p.x + p.y) * 2.5 + t * 0.7)
            + sin(length(p) * (5.0 + 3.0 * u_mid) - t * 2.0);
    vec3 col = 0.5 + 0.5 * cos(3.14159 * v + vec3(0.0, 2.094, 4.188) + u_time * 0.3);
    col *= 0.4 + 0.9 * u_level;
    gl_FragColor = vec4(col, 1.0);
}
