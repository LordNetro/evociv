uniform float uLineWidth;
uniform float uLineSpacing;

varying vec3 vColor;
varying vec3 vLocalPos;

void main() {
    // Each instance is a 1x1 box; local xz ranges from -0.5 to 0.5
    vec2 coord = (vLocalPos.xz + 0.5) * uLineSpacing;
    vec2 dist = abs(fract(coord - 0.5) - 0.5);
    vec2 dx = fwidth(coord);
    float line = smoothstep(uLineWidth + dx.x, uLineWidth - dx.x, dist.x)
               + smoothstep(uLineWidth + dx.y, uLineWidth - dx.y, dist.y);
    float edge = clamp(line, 0.0, 1.0);
    
    vec3 color = vColor * (1.0 - edge * 0.25);
    gl_FragColor = vec4(color, 1.0);
}
