uniform float uTime;
uniform float uPulseSpeed;

varying float vAlpha;

void main() {
    float pulse = sin(uTime * uPulseSpeed) * 0.5 + 0.5;
    float scale = 1.0 + pulse * 0.15;
    vec3 pos = position * scale;
    vAlpha = 0.6 + pulse * 0.4;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
}
