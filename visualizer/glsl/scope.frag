// Synchrofazotron glsl preset: scope — an audio oscilloscope on a phosphor
// grid. The trace is synthesized from the three bands (no raw samples are
// exposed), so bass/mid/treble bend, wobble and shimmer the line.
#ifdef GL_ES
precision mediump float;
#endif

uniform vec2 u_resolution;
uniform float u_time;
uniform float u_level;
uniform float u_bass;
uniform float u_mid;
uniform float u_treble;

float wave(float x) {
    return u_bass   * 0.45 * sin(x * 3.0  + u_time * 2.0)
         + u_mid    * 0.30 * sin(x * 11.0 - u_time * 3.5)
         + u_treble * 0.18 * sin(x * 27.0 + u_time * 6.0);
}

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;          // 0..1
    vec2 p = uv * 2.0 - 1.0;                            // -1..1
    p.x *= u_resolution.x / u_resolution.y;            // keep the aspect square

    vec3 col = vec3(0.0, 0.02, 0.01);

    // graticule (scope grid) + brighter center axes
    vec2 g = abs(fract(uv * vec2(12.0, 8.0)) - 0.5);
    col += vec3(0.0, 0.15, 0.06) * smoothstep(0.47, 0.5, max(g.x, g.y)) * 0.3;
    col += vec3(0.0, 0.25, 0.10) *
           (smoothstep(0.012, 0.0, abs(p.y)) + smoothstep(0.012, 0.0, abs(p.x)));

    // the trace: distance to y = wave(x), a bright core plus phosphor glow
    float d = abs(p.y - wave(p.x));
    float line = smoothstep(0.06, 0.0, d);
    float glow = 0.035 / (d + 0.035);
    col += vec3(0.25, 1.0, 0.45) * (line + glow * 0.5) * (0.5 + 0.8 * u_level);

    col *= 0.9 + 0.1 * sin(gl_FragCoord.y * 3.14159);  // scanlines
    gl_FragColor = vec4(col, 1.0);
}
