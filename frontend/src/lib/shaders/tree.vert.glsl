uniform float uTime;
uniform float uWindStrength;
uniform float uWindFrequency;

varying vec3 vNormal;
varying vec3 vViewPos;

void main() {
    vec3 pos = position;
    // Sway: more at top, less at base
    float height = max(pos.y, 0.0);
    float sway = sin(pos.x * uWindFrequency + uTime * 1.5) * uWindStrength * height
               + cos(pos.z * uWindFrequency * 0.7 + uTime * 1.2) * uWindStrength * 0.6 * height;
    pos.x += sway;
    pos.z += sway * 0.3;
    
    vec4 mvPos = modelViewMatrix * vec4(pos, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vViewPos = mvPos.xyz;
    gl_Position = projectionMatrix * mvPos;
}
