# Design: 3D Rendering Migration

## Technical Approach

Replace the custom Canvas 2D engine loop (`Engine`, `Entities`, `Grid`, `Camera`) with a declarative Threlte 8 component tree inside a single `<Canvas>` mount. The simulation store (Svelte writable) feeds reactive props into Threlte components via Svelte 5 `$derived`/`$effect`. OrbitControls provides free 3D camera. Existing overlay panels remain untouched — they render above the canvas via CSS `position: fixed` with `z-index`.

## Architecture Decisions

### Decision: Threlte 8 vs raw Three.js

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Threlte 8 + Three.js | Declarative component tree, Svelte 5 runes compatible, built-in reactivity | **Chosen** — aligns with Svelte 5 paradigm, reduces boilerplate |
| Raw Three.js | Full control, no abstraction overhead | Rejected — imperative setup code, manual lifecycle, no reactivity bridge |
| Three.js via `svelte:this` + manual tick | Works but fights Svelte's reactivity model | Rejected — higher maintenance, no community patterns |

**Rationale**: Threlte 8 targets Svelte 5 natively (Runes API). The project already uses Svelte 5.55. Threlte's `<Canvas>` auto-manages the render loop, resize, and disposal — replacing our custom `Engine` class.

### Decision: WebGL vs WebGPU

| Option | Tradeoff | Decision |
|--------|----------|----------|
| WebGL (Three.js r184) | Max browser compat, stable API | **Chosen** |
| WebGPU | Better perf, future-facing | Rejected — Chrome/Edge only, no IE/Safari fallback, overkill for flat grid + spheres |

**Rationale**: The MVP renders basic primitives (spheres, boxes, cones, planes) — WebGL handles these at 60fps with no GPU pressure. WebGPU adds bundle size and complexity with zero visual benefit.

### Decision: InstancedMesh for grid tiles

**Choice**: Use `THREE.InstancedMesh` for all grid tiles (single draw call vs 2500 individual meshes for 50×50).
**Alternatives considered**: Individual meshes per tile (simple but 2500+ draw calls), merged geometry (harder to update per-tile color).
**Rationale**: Grid tiles share geometry (PlaneGeometry) and differ only by position and color — the exact use case for instancing. Updates per tile (resource changes) write to the instance matrix/color buffer without rebuilding geometry.

## Data Flow

```
WebSocket ──→ simulationStore.updateFromSnapshot(data)
                      │
                      ▼
               simulationStore (writable)
                      │
            ┌─────────┼──────────────┐
            │         │              │
            ▼         ▼              ▼
        Grid3D    Agents3D      WaterPlane
      ($derived)  ($derived)    ($derived)
            │         │              │
            │    uiStore.selectAgent()──→ SelectionHighlight
            │              │
            ▼              ▼
      Resources3D    AgentLabel
      ($derived)    (HTML sprites)
```

- All 3D components subscribe to `simulationStore` via `$derived` (auto-subscribe from Svelte stores in `.svelte` files).
- Agent click: raycaster from Threlte's `useThrelte` → calls `uiStore.selectAgent(id)`.
- `SelectionHighlight` reads `$uiStore.selectedAgentId` and positions a `RingGeometry` at the matching agent's coordinates.
- Positions are interpolated in `canvas3dStore.svelte.js` (lerp on tick updates, ~200ms).

## Component Architecture

```
SimCanvas.svelte
  └─ <Canvas>
       └─ Scene.svelte
            ├─ AmbientLight + DirectionalLight
            ├─ OrbitControls (pan, rotate, zoom)
            ├─ Grid3D.svelte (InstancedMesh planes)
            │   └─ Resources3D.svelte (primitives on tiles)
            ├─ WaterPlane.svelte (transparent planes)
            ├─ Agents3D.svelte (spheres + faction rings)
            │   └─ SelectionHighlight.svelte (ring on selected)
            └─ AgentLabel.svelte (HTML sprites via @threlte/extras)
```

### Component Responsibilities

| Component | Role | Key Tech |
|-----------|------|----------|
| `Scene.svelte` | Root scene: lights, camera, controls, `<T.PerspectiveCamera>`, `<OrbitControls>` | Threlte `<T.Canvas>`, auto-resize |
| `Grid3D.svelte` | Instanced planes for all tiles, color per instance | `InstancedMesh`, `$derived(tiles)` |
| `Resources3D.svelte` | Cone/bow/box/sphere on resource tiles at tile center + `y=0` | `MathUtils` geometry, positioned transforms |
| `Agents3D.svelte` | Spheres by role color, faction ring borders, child scale 0.6 | `SphereGeometry`, `LineLoop` for rings |
| `AgentLabel.svelte` | HTML text sprites above agents (name initial) | `<T.Html>` from `@threlte/extras` |
| `WaterPlane.svelte` | Semi-transparent blue planes, subtle animation | `PlaneGeometry`, `MeshStandardMaterial` with opacity |
| `SelectionHighlight.svelte` | Yellow `RingGeometry` + `LineLoop` around selected agent | Tracks `$uiStore.selectedAgentId` |

## Coordinate Mapping

- Grid tile `(tx, ty)` → 3D position `(tx * tileSize, 0, ty * tileSize)`
- Agents elevated `y = 0.5` (half a tile height above surface)
- Resources at tile center `y = 0` (flush with tile surface)
- `tileSize = 32` world units (matching current config constant)

## Integration with Svelte 5

- `Scene.svelte` uses `$props()` to receive `gridWidth`, `gridHeight`, `tileSize`.
- Threlte components read store state via `$derived($simulationStore.tiles)` — the `$` prefix auto-subscribes to Svelte writable stores inside `.svelte` files.
- `$effect` handles side effects: animation loops, interpolation tickers, raycaster setup.
- `canvas3dStore.svelte.js` holds interpolation state (previous → target positions) and runs a `requestAnimationFrame` loop for smooth agent movement.

## Performance Strategy

| Concern | Approach |
|---------|----------|
| Draw calls | `InstancedMesh` for all tiles (1 call regardless of grid size) |
| Culling | Three.js built-in frustum culling (enabled by default) |
| Bundle size | Dynamic import of Threlte/Three.js: `const Canvas = await import('@threlte/core')` in `SimCanvas.svelte`'s `onMount` |
| GPU load | No shadows, no post-processing, flat lighting — MVP targets 60fps on integrated GPU |
| Geometry limit | Only instantiate geometry for tiles with resources (not all 2500 tiles need cones/boxes) |

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/lib/canvas3d/Scene.svelte` | Create | Root Threlte scene with Canvas, lights, OrbitControls |
| `frontend/src/lib/canvas3d/Grid3D.svelte` | Create | InstancedMesh grid tiles with per-instance color |
| `frontend/src/lib/canvas3d/Resources3D.svelte` | Create | Resource primitives (cones, boxes, spheres, planes) |
| `frontend/src/lib/canvas3d/Agents3D.svelte` | Create | Agent spheres with role colors, faction rings, child scale |
| `frontend/src/lib/canvas3d/AgentLabel.svelte` | Create | HTML labels via `<T.Html>` |
| `frontend/src/lib/canvas3d/WaterPlane.svelte` | Create | Semi-transparent animated water |
| `frontend/src/lib/canvas3d/SelectionHighlight.svelte` | Create | Yellow ring on selected agent |
| `frontend/src/lib/canvas3d/canvas3dStore.svelte.js` | Create | Interpolation state + tick loop for smooth movement |
| `frontend/src/lib/components/SimCanvas.svelte` | Modify | Replace Engine class with Threlte `<Canvas>` mount |
| `frontend/src/lib/canvas/engine.ts` | Delete | No longer needed — Threlte manages render loop |
| `frontend/src/lib/canvas/grid.ts` | Delete | Replaced by Grid3D, Resources3D, WaterPlane |
| `frontend/src/lib/canvas/entities.ts` | Delete | Replaced by Agents3D, AgentLabel |
| `frontend/src/lib/canvas/camera.ts` | Delete | Replaced by OrbitControls |
| `frontend/src/lib/canvas/animation.ts` | Delete | `lerp`/`clamp` utilities moved to canvas3dStore if needed |
| `frontend/package.json` | Modify | Add `@threlte/core`, `@threlte/extras`, `three` as dependencies |

### SimCanvas.svelte Migration

```svelte
<!-- BEFORE: imperative Engine class -->
<script lang="ts">
  import { Engine } from '$lib/canvas/engine';
  let canvas: HTMLCanvasElement;
  let engine: Engine;
  $effect(() => { engine = new Engine(canvas, config); ... });
</script>
<canvas bind:this={canvas} />

<!-- AFTER: declarative Threlte Canvas -->
<script lang="ts">
  import Scene from '$lib/canvas3d/Scene.svelte';
</script>
<Scene {config} />
```

The `<canvas>` element is now managed internally by Threlte's `<T.Canvas>` — no manual `getContext('2d')`, `requestAnimationFrame`, resize listeners, or cleanup needed. Threlte handles all of that.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Component | Each Threlte component mounts without error | Vitest + jsdom, verify no WebGL errors in console |
| Integration | Click raycaster sets `uiStore.selectedAgentId` | Simulate pointer event on Threlte Canvas, assert store update |
| Render | Grid/agents render with correct colors | Snapshot Three.js scene graph (object counts, material colors) |
| Performance | 50×50 grid + 20 agents at ≥30fps | Manual benchmark with `stats.js` overlay, monitor `renderer.info` |

## Migration / Rollout

No migration required — this is a pure frontend swap. Both the old 2D engine and new Threlte renderer consume the same `simulationStore`. Rollback: revert `SimCanvas.svelte`, restore `src/lib/canvas/`, remove `canvas3d/` and Threlte deps.

## Open Questions

- [ ] None — all decisions documented and aligned with specs.
