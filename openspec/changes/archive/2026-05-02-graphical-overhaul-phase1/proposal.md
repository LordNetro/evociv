# Proposal: Graphical Overhaul Phase 1

## Intent

~225-265 draw calls/frame from 220 individual meshes + stock MeshStandardMaterial everywhere + CPU-driven animation (useTask). Phase 1 targets GPU-driven custom ShaderMaterials, InstancedMesh optimization, and scene atmosphere (fog + toneMapping).

## Scope

### In Scope
- **Water shader** — Custom ShaderMaterial: Gerstner waves + Fresnel rim (replaces flat PlaneGeometry)
- **Selection glow shader** — GPU pulse + emissive glow (removes CPU useTask)
- **Fog + toneMapping** — FogExp2 + ACESFilmicToneMapping (2 lines Three.js config)
- **Grid shading** — ShaderMaterial overlay on InstancedMesh
- **Agent shared materials** — One material per role color + Fresnel rim edge glow
- **Tree sway shader** — GPU vertex animation for canopies
- **InstancedMesh for resources** — 220 individual meshes → ~5 InstancedMeshes by resource type

### Out of Scope
Shadows, post-processing (bloom/DOF), terrain shaders, particles, skeletal animation — all deferred to Phase 2+.

## Capabilities

### New Capabilities
- `shader-effects`: Custom ShaderMaterial for water, selection glow, grid overlay, tree sway — GPU-driven animated visuals
- `resource-instancing`: InstancedMesh consolidation for resources (220→~5 draw calls)

### Modified Capabilities
- `3d-rendering`: Add fog + toneMapping to scene configuration; shared agent materials replace per-agent materials

## Approach

GPU-driven animation via vertex/fragment shaders. Zero new dependencies — pure Three.js ShaderMaterial. Progressive enhancement: shaders stack on existing architecture, replacing individual component internals. Instancing groups 220 resource meshes by type into consolidated InstancedMeshes.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `frontend/src/lib/canvas3d/WaterPlane.svelte` | Modified | ShaderMaterial replaces MeshStandardMaterial |
| `frontend/src/lib/canvas3d/SelectionHighlight.svelte` | Modified | GPU pulse shader replaces useTask ring |
| `frontend/src/lib/canvas3d/Scene.svelte` | Modified | Add FogExp2 + ACESFilmicToneMapping |
| `frontend/src/lib/canvas3d/Grid3D.svelte` | Modified | ShaderMaterial grid line overlay |
| `frontend/src/lib/canvas3d/Agents3D.svelte` | Modified | Shared materials per role + Fresnel rim |
| `frontend/src/lib/canvas3d/Resources3D.svelte` | Modified | InstancedMesh refactor (220→~5) |
| `frontend/src/lib/canvas3d/Trees3D.svelte` | Modified | Vertex shader sway animation |
| `frontend/src/lib/canvas3d/shaders/` | New | GLSL chunk directory (water, glow, grid, sway) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| GPU incompatibility (older GPUs, WebGL 1) | Low | Fallback to stock materials via capabilities detection |
| Instancing breaks resource click interaction | Medium | Raycasting on InstancedMesh + instanceId mapping |
| Water shader perf on integrated GPUs | Low | LOD uniform to reduce wave count |

## Rollback Plan

Each shader component wraps existing stock material — revert individual `.svelte` files with `git checkout HEAD -- <file>`. InstancedMesh change keeps parallel `Resources3D.legacy.svelte` during transition. No global state changes; rollback is per-component.

## Dependencies

- Three.js r184 (already in use) — ShaderMaterial, InstancedMesh, FogExp2, ACESFilmicToneMapping

## Success Criteria

- [ ] Draw calls reduced from 225-265 to <80 (InstancedMesh + shared materials)
- [ ] Water renders with animated Gerstner waves + Fresnel rim
- [ ] Selection ring pulses via GPU shader (no useTask in component)
- [ ] Fog + toneMapping visible in scene
- [ ] Grid overlay renders via ShaderMaterial
- [ ] Tree canopies sway via GPU vertex shader
- [ ] No regressions in agent selection, resource count display
- [ ] `svelte-check` + backend tests pass
