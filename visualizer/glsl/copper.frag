// Synchrofazotron glsl preset: copper — Amiga copper bars + scanlines.
#ifdef GL_ES
precision mediump float;
#endif

uniform vec2 u_resolution;
uniform float u_time;
uniform float u_level;
uniform float u_bass;
uniform float u_mid;
uniform float u_treble;

vec3 bar(vec2 uv, float phase, float speed, vec3 tint) {
    float y = 0.5 + 0.38 * sin(u_time * speed + phase) * (0.6 + 0.8 * u_bass);
    float d = abs(uv.y - y);
    return tint * smoothstep(0.09, 0.0, d) * (0.5 + 0.9 * u_level);
}

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;
    vec3 col = vec3(0.02, 0.00, 0.05);
    col += bar(uv, 0.0, 1.1, vec3(1.0, 0.1, 0.1));
    col += bar(uv, 1.3, 1.4, vec3(1.0, 0.6, 0.0));
    col += bar(uv, 2.6, 1.7, vec3(0.1, 1.0, 0.2));
    col += bar(uv, 3.9, 2.0, vec3(0.1, 0.4, 1.0));
    col += bar(uv, 5.2, 2.3, vec3(0.8, 0.1, 1.0));
    col *= 0.85 + 0.15 * sin(gl_FragCoord.y * 3.14159);  // CRT scanlines
    gl_FragColor = vec4(col, 1.0);
}
