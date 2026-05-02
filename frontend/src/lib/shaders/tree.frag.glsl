uniform vec3 uColor;
uniform vec3 uShadowColor;

varying vec3 vNormal;
varying vec3 vViewPos;

void main() {
    vec3 viewDir = normalize(-vViewPos);
    vec3 normal = normalize(vNormal);
    
    // Simple hemisphere lighting
    float light = dot(normal, normalize(vec3(0.5, 1.0, 0.3))) * 0.5 + 0.5;
    vec3 color = mix(uShadowColor, uColor, light);
    
    gl_FragColor = vec4(color, 1.0);
}
