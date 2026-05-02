uniform float uTime;
uniform float uWaveSpeed;
uniform float uWaveAmp;

varying vec3 vNormal;
varying vec3 vPosition;
varying vec2 vUv;

void main() {
    vec3 pos = position;
    float wave1 = sin(pos.x * 2.0 + uTime * uWaveSpeed) * uWaveAmp;
    float wave2 = cos(pos.z * 1.7 + uTime * uWaveSpeed * 0.8) * uWaveAmp * 0.6;
    float wave3 = sin((pos.x + pos.z) * 1.2 + uTime * uWaveSpeed * 0.5) * uWaveAmp * 0.3;
    pos.y += wave1 + wave2 + wave3;
    
    // Approximate normal from wave derivatives
    float dx = cos(pos.x * 2.0 + uTime * uWaveSpeed) * uWaveAmp * 2.0;
    float dz = -sin(pos.z * 1.7 + uTime * uWaveSpeed * 0.8) * uWaveAmp * 1.7 * 0.6;
    vec3 newNormal = normalize(vec3(-dx, 1.0, -dz));
    
    vNormal = normalize(normalMatrix * newNormal);
    vPosition = (modelViewMatrix * vec4(pos, 1.0)).xyz;
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
}
