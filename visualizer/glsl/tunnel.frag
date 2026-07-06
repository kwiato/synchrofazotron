// Synchrofazotron glsl preset: tunnel — checkerboard fly-through, bass = speed.
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
    float a = atan(p.y, p.x);
    float r = max(length(p), 1e-3);
    float t = u_time * (0.6 + 1.5 * u_bass);
    float x = 0.4 / r + t;               // depth along the tunnel
    float y = a * 3.8197;                // 12 segments around (12 / pi)
    float c = mod(floor(x * 4.0) + floor(y), 2.0);
    vec3 col = mix(vec3(0.10, 0.00, 0.25), vec3(1.00, 0.20, 0.90), c);
    col = mix(col, vec3(0.2, 1.0, 1.0), u_treble * 0.5);
    col *= (0.3 + 0.9 * u_level) * smoothstep(0.0, 0.35, r);  // dark core = depth
    gl_FragColor = vec4(col, 1.0);
}
