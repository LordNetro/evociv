uniform vec3 uColor;
uniform vec3 uGlowColor;
uniform float uTime;

varying float vAlpha;

void main() {
    float glow = sin(uTime * 2.0) * 0.3 + 0.7;
    vec3 color = mix(uColor, uGlowColor, glow * 0.3);
    gl_FragColor = vec4(color, vAlpha);
}
