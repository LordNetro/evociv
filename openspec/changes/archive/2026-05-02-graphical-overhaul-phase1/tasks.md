# Tasks: Graphical Overhaul Phase 1

## Phase 1: Shader Files + Scene Atmosphere

- [x] 1.1 Create `shaders/water.vert.glsl` — Gerstner wave vertex displacement, uTime/uAmplitude/uFrequency/uSpeed uniforms, view-vector varying for Fresnel
- [x] 1.2 Create `shaders/water.frag.glsl` — scrolling UV offset via uTime, blue-white Fresnel rim via dot(normal, viewDir), transparent alpha output
- [x] 1.3 Create `shaders/pulse.vert.glsl` — breathing vertex scale via uTime sine wave
- [x] 1.4 Create `shaders/pulse.frag.glsl` — emissive gold glow via uColor/uIntensity uniforms
- [x] 1.5 Create `shaders/grid.vert.glsl` — subtle vertex height variation from world xz via uHeightScale
- [x] 1.6 Create `shaders/grid.frag.glsl` — anti-aliased grid lines via smoothstep(fwidth(), uv), uLineSpacing/uLineWidth uniforms
- [x] 1.7 Create `shaders/tree.vert.glsl` — sinusoidal sway with pivot-at-base falloff, uWindStrength/uWindFrequency/uTime
- [x] 1.8 Create `shaders/tree.frag.glsl` — foliage green with optional vertex-position color variation
- [x] 1.9 Modify `Scene.svelte` — add `FogExp2(0x1a1a2e, 0.008)` to scene, set `renderer.toneMapping = ACESFilmicToneMapping` + `toneMappingExposure = 1.0`

## Phase 2: Component Modifications

- [x] 2.1 Modify `WaterPlane.svelte` — replace MeshStandardMaterial with ShaderMaterial(water.glsl), add `useTask` for uTime uniform
- [x] 2.2 Modify `SelectionHighlight.svelte` — remove CPU useTask rotation/scale, use ShaderMaterial(pulse.glsl) with uTime-only useTask
- [x] 2.3 Modify `Grid3D.svelte` — apply ShaderMaterial(grid.glsl) overlay on InstancedMesh, keep instance update + frustumCulled logic
- [x] 2.4 Modify `Agents3D.svelte` — add `ROLE_MATERIALS` cache per role color, inject Fresnel rim via `onBeforeCompile` (vNormal/vViewPosition varyings + rim uniforms), preserve click interactivity

## Phase 3: Resources Rewrite

- [x] 3.1 Rewrite `Resources3D.svelte` — 8 InstancedMeshes (tree_trunk, tree_canopy, berry, stone, iron_ore, clay, sand, fiber) from `RESOURCE_GEO` map, per-instance position matrix + color attribute
- [x] 3.2 Apply tree sway — tree_canopy InstancedMesh gets ShaderMaterial(tree.glsl) with uTime/uWindStrength/uWindFrequency from useTask; tree_trunk uses stock MeshStandardMaterial
- [x] 3.3 Add instanceId→resource mapping for raycasting; ensure instance clicks resolve to resource data
- [x] 3.4 Remove old per-resource `<T.Mesh>` elements and `RESOURCE_TYPES` filter

## Phase 4: Verification

- [x] 4.1 Run `svelte-check` — validate all shader uniform types and component bindings
- [x] 4.2 Run `npm run build` — confirm GLSL raw imports bundle correctly
- [x] 4.3 Manual QA — water animates, fog+toneMapping visible, selection ring pulses (no useTask CPU), grid lines render, agents clickable, all 7 resource types distinct and visible
