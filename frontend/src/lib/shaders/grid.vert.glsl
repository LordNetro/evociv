uniform float uTime;
uniform float uHeightScale;

varying vec3 vColor;
varying vec3 vLocalPos;

void main() {
    #ifdef USE_INSTANCING_COLOR
        vColor = instanceColor;
    #else
        vColor = vec3(0.5);
    #endif
    
    vec3 pos = position;
    float h = sin(pos.x * 0.5 + uTime * 0.1) * cos(pos.z * 0.7 + uTime * 0.15) * uHeightScale;
    pos.y += h;
    vLocalPos = pos;
    
    gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
}
