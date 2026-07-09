// Synchrofazotron glsl preset: cube — a rotating rounded cube raymarched from an
// SDF; bass drives the spin and the pulse. Audio uniforms come from
// glsl-audio-bridge.py (0..1, fast attack/slow decay).
//
// Perf: the old version rotated the sample point *inside* map(), so the two
// sin/cos ran on every one of ~50 marches + normal taps per pixel (~100 trig
// ops/pixel — the bottleneck on the Pi's GPU). Rotations are isometries, so we
// instead rotate the ray (and the light) into the cube's frame once per pixel
// and march an axis-aligned box; map() is now pure SDF, no trig in the loop.
#ifdef GL_ES
precision mediump float;
#endif

uniform vec2 u_resolution;
uniform float u_time;
uniform float u_level;
uniform float u_bass;
uniform float u_mid;
uniform float u_treble;

mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }

float sdBox(vec3 p, vec3 b) {
    vec3 d = abs(p) - b;
    return length(max(d, 0.0)) + min(max(d.x, max(d.y, d.z)), 0.0);
}

float map(vec3 p) {                          // p is already in the cube's frame
    float s = 0.65 + 0.20 * u_bass;          // pulse with the beat
    return sdBox(p, vec3(s)) - 0.03;         // slightly rounded edges
}

vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.002, 0.0);
    return normalize(vec3(
        map(p + e.xyy) - map(p - e.xyy),
        map(p + e.yxy) - map(p - e.yxy),
        map(p + e.yyx) - map(p - e.yyx)));
}

// Rotate a vector into the cube's local frame (same order the old map() used).
vec3 toLocal(vec3 v, mat2 r1, mat2 r2) {
    v.xz = r1 * v.xz;
    v.xy = r2 * v.xy;
    return v;
}

void main() {
    mat2 r1 = rot(u_time * 0.6 + u_bass * 2.0);
    mat2 r2 = rot(u_time * 0.45);

    vec2 uv = (2.0 * gl_FragCoord.xy - u_resolution) / min(u_resolution.x, u_resolution.y);
    vec3 ro = toLocal(vec3(0.0, 0.0, 3.2), r1, r2);            // camera, in frame
    vec3 rd = toLocal(normalize(vec3(uv, -1.6)), r1, r2);      // ray, in frame
    vec3 lig = toLocal(normalize(vec3(0.6, 0.7, 0.5)), r1, r2); // light, in frame

    float t = 0.0;
    float hit = 0.0;
    for (int i = 0; i < 40; i++) {
        float d = map(ro + rd * t);
        if (d < 0.001) { hit = 1.0; break; }
        t += d;
        if (t > 6.0) break;
    }

    vec3 col = vec3(0.02, 0.01, 0.05) + 0.04 * u_level;   // faint glowing void
    if (hit > 0.5) {
        vec3 p = ro + rd * t;
        vec3 n = calcNormal(p);
        float dif = 0.4 + 0.6 * max(dot(n, lig), 0.0);
        vec3 face = 0.5 + 0.5 * cos(vec3(0.0, 2.094, 4.188) + abs(n) * 3.0 + u_time * 0.3);
        col = face * dif * (0.5 + 0.9 * u_level);
        col += u_treble * 0.7 * pow(max(dot(n, lig), 0.0), 8.0);  // treble sparkle
    }
    gl_FragColor = vec4(col, 1.0);
}
