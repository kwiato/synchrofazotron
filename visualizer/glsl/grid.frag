// Synchrofazotron glsl preset: grid — a synthwave perspective grid racing
// toward a retro sun. Bass sets the scroll speed, treble tints the lines.
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
    vec2 uv = (2.0 * gl_FragCoord.xy - u_resolution) / u_resolution.y;
    vec3 col;

    if (uv.y > 0.0) {                        // sky + sun
        col = mix(vec3(0.16, 0.02, 0.30), vec3(0.02, 0.0, 0.08), clamp(uv.y, 0.0, 1.0));
        float sun = smoothstep(0.42, 0.0, length(uv - vec2(0.0, 0.30)));
        col += vec3(1.0, 0.45, 0.15) * sun * (0.8 + 0.6 * u_mid);
    } else {                                 // ground plane, projected to a floor
        vec2 gp = vec2(uv.x, 1.0) / (-uv.y + 0.06);
        gp.y += u_time * (1.0 + 2.0 * u_bass);
        vec2 f = abs(fract(gp) - 0.5);
        float grid = smoothstep(0.06, 0.0, min(f.x, f.y));
        vec3 gc = mix(vec3(0.9, 0.0, 0.7), vec3(0.0, 0.9, 1.0), 0.5 + 0.5 * u_treble);
        float fade = smoothstep(0.0, -0.9, uv.y);   // dark at the horizon
        col = gc * grid * fade * (0.5 + 0.8 * u_level);
    }
    gl_FragColor = vec4(col, 1.0);
}
