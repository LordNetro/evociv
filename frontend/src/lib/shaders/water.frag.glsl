uniform vec3 uColor;
uniform vec3 uDeepColor;
uniform float uTime;

varying vec3 vNormal;
varying vec3 vPosition;
varying vec2 vUv;

void main() {
    vec3 viewDir = normalize(-vPosition);
    vec3 normal = normalize(vNormal);
    
    // Fresnel rim
    float rim = 1.0 - max(dot(normal, viewDir), 0.0);
    rim = pow(rim, 3.0);
    
    // Animated specular-like highlight
    vec2 uv = vUv * 3.0 + uTime * 0.02;
    float spec = sin(uv.x * 10.0) * cos(uv.y * 8.0) * 0.15 + 0.15;
    
    vec3 waterColor = mix(uDeepColor, uColor, rim);
    waterColor += spec * vec3(0.8, 0.9, 1.0);
    
    float alpha = 0.8 + rim * 0.2;
    gl_FragColor = vec4(waterColor, alpha);
}
