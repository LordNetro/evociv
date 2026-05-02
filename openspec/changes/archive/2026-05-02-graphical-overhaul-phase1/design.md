# Design: Graphical Overhaul Phase 1

## Technical Approach

Replace CPU-driven rendering (~225-265 draw calls from 220 individual meshes + per-frame `useTask` animations) with GPU-driven ShaderMaterials + InstancedMesh consolidation. Zero new dependencies — pure Three.js r184 APIs. Each component wraps its stock material internally so rollback is per-file.

**Correction from proposal**: `Trees3D.svelte` does not exist. Trees (trunk + canopy) are rendered inside `Resources3D.svelte`. Tree sway integrates directly into that component's InstancedMesh refactor.

## Architecture Decisions

### Decision: InstancedMesh Per Resource Type

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Single merged InstancedMesh with all types | One draw call, but type-specific geometry impossible | ❌ Rejected |
| One InstancedMesh per type | ~8 draw calls vs. 220; simpler per-type geometry + material + sway | ✅ **Selected** |
| One InstancedMesh + instance attributes for geometry switching | Requires custom shader to select geo per instance; complex | ❌ Rejected |

### Decision: Fresnel via onBeforeCompile (Agents)

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Full ShaderMaterial replacement | Loses PBR lighting (env maps, shadows in Phase 2) | ❌ Rejected |
| `onBeforeCompile` injection on MeshStandardMaterial | Preserves PBR, adds rim in vertex/fragment chunks | ✅ **Selected** |
| Post-process rim pass | Requires full-screen pass; overkill for agent highlight | ❌ Rejected |

### Decision: Water Material

| Option | Tradeoff | Decision |
|--------|----------|----------|
| MeshStandardMaterial with vertex shader override | Deformation possible via `onBeforeCompile` but no control over alpha/Fresnel in fragment | ❌ Rejected |
| Full ShaderMaterial | Custom vertex deformation + Fresnel + alpha; no PBR needed for water | ✅ **Selected** |

### Decision: GLSL as `.glsl` Files vs. Template Literals

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Inline template literals in `.svelte` | No syntax highlighting; hard to maintain | ❌ Rejected |
| External `.glsl` files imported as strings | Syntax highlighting in editors; Vite loads raw via `?raw` | ✅ **Selected** |

### Decision: Tree Sway Location

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `Trees3D.svelte` (as proposed) | File does not exist; would split tree rendering across two components | ❌ Rejected |
| Inside `Resources3D.svelte` InstancedMesh | Tree canopy InstancedMesh gets sway vertex shader; trunk stays static | ✅ **Selected** |

## Data Flow

```
Snapshot (WebSocket)
    │
    ├─→ Grid3D: tiles[] → InstancedMesh position + color attributes
    ├─→ WaterPlane: waterTiles[] → bounding box → ShaderMaterial plane
    ├─→ Resources3D: resources[] → 8 InstancedMeshes by type
    │       └── canopy → sway vertex shader (uTime)
    ├─→ Agents3D: agents[] → shared ROLE_MATERIALS + MeshStandardMaterial.onBeforeCompile
    └─→ SelectionHighlight: uiStore.selectedAgentId → position → ShaderMaterial ring

Scene.svelte: renderer.toneMapping + scene.fog (applied in createRenderer)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/lib/shaders/water.vert.glsl` | Create | Gerstner wave vertex deformation |
| `frontend/src/lib/shaders/water.frag.glsl` | Create | Fresnel rim + alpha water color |
| `frontend/src/lib/shaders/pulse.vert.glsl` | Create | Selection ring breathing scale |
| `frontend/src/lib/shaders/pulse.frag.glsl` | Create | Emissive gold pulse glow |
| `frontend/src/lib/shaders/grid.vert.glsl` | Create | Grid line derivative calculation |
| `frontend/src/lib/shaders/grid.frag.glsl` | Create | Anti-aliased grid line overlay |
| `frontend/src/lib/shaders/sway.vert.glsl` | Create | Tree canopy wind sway via sin(pos.xz + time) |
| `frontend/src/lib/canvas3d/WaterPlane.svelte` | Modify | ShaderMaterial with `.glsl` imports + `useTask` for uTime |
| `frontend/src/lib/canvas3d/SelectionHighlight.svelte` | Modify | Replace `useTask` rotation/scale with ShaderMaterial pulse |
| `frontend/src/lib/canvas3d/Scene.svelte` | Modify | `renderer.toneMapping = ACESFilmicToneMapping` + `scene.fog = FogExp2` |
| `frontend/src/lib/canvas3d/Grid3D.svelte` | Modify | ShaderMaterial overlay; subtle height variation in vertex |
| `frontend/src/lib/canvas3d/Agents3D.svelte` | Modify | `ROLE_MATERIALS` cache + `onBeforeCompile` Fresnel injection |
| `frontend/src/lib/canvas3d/Resources3D.svelte` | Rewrite | 8 InstancedMeshes (tree_trunk, tree_canopy, berry, stone, iron_ore, clay, sand, fiber) + sway on canopy |

## Interfaces / Contracts

```typescript
// Shared material cache (in Agents3D.svelte or separate module)
const ROLE_MATERIALS = new Map<string, MeshStandardMaterial>();

function getRoleMaterial(role: string): MeshStandardMaterial {
  if (!ROLE_MATERIALS.has(role)) {
    const mat = new MeshStandardMaterial({ color: ROLE_COLORS[role] });
    // Inject Fresnel rim via onBeforeCompile
    mat.onBeforeCompile = (shader) => {
      shader.vertexShader = shader.vertexShader.replace(
        '#include <common>',
        'varying vec3 vViewPosition; varying vec3 vNormal; #include <common>'
      );
      // ... inject rim uniform + fragment logic
    };
    ROLE_MATERIALS.set(role, mat);
  }
  return ROLE_MATERIALS.get(role)!;
}
```

```typescript
// Resource type → geometry mapping
const RESOURCE_GEO: Record<string, { geo: BufferGeometry; height: number }> = {
  tree_trunk:  { geo: new CylinderGeometry(0.08, 0.1, 0.3),  height: 0.3 },
  tree_canopy: { geo: new ConeGeometry(0.4, 0.8),            height: 0.8 },
  berry:       { geo: new SphereGeometry(0.2),               height: 0.2 },
  stone:       { geo: new BoxGeometry(0.35, 0.25, 0.35),     height: 0.25 },
  iron_ore:    { geo: new DodecahedronGeometry(0.2),         height: 0.2 },
  clay:        { geo: new BoxGeometry(0.3, 0.2, 0.3),        height: 0.2 },
  sand:        { geo: new BoxGeometry(0.25, 0.15, 0.25),     height: 0.15 },
  fiber:       { geo: new CylinderGeometry(0.03, 0.04, 0.35), height: 0.35 },
};
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Type check | All shader uniforms match `.glsl` usage | `svelte-check` |
| Visual | Water animates, fog visible, grid lines render | Manual QA in browser |
| Regression | Agents clickable, selection ring visible | Manual QA |
| Build | All `.glsl` files import correctly as raw strings | `vite build` |

No frontend test framework installed — visual + type-check validation only (per `openspec/config.yaml`).

## Migration / Rollout

No migration. Legacy `Resources3D.svelte` does not exist — but for safety, keep a git backup before the rewrite so the original 220-individual-mesh version is recoverable via `git checkout`.

## Open Questions

- [ ] Should tree canopy sway affect the trunk InstancedMesh too? (Design says no — trunk stays still, canopy sways)
- [ ] iron_ore / clay / sand / fiber color values — need final art direction or use reasonable defaults?
