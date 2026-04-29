# Proposal: 3d-rendering-migration

## Intent

Replace Canvas 2D rendering with Threlte 8 + Three.js (WebGL) to unlock 3D camera, better visual clarity, and an extensible scene graph for future features (particles, day/night, terrain height).

## Scope

### In Scope
- 7 Threlte components in `src/lib/canvas3d/`: Scene, Agents3D, Grid3D, AgentLabel, WaterPlane, SelectionHighlight, store
- OrbitControls for free 3D camera (pan, rotate, zoom)
- Geometries: spheres = agents, cones = trees, planes = tiles, boxes = stone
- Same `simulationStore` as data source (delta snapshots unchanged)
- SimCanvas.svelte rewired to mount Threlte Canvas
- Agent selection via raycasting → `uiStore.selectAgent()`

### Out of Scope
- Terrain height variation (flat grid for MVP)
- Day/night cycle, skybox, particles
- glTF/GLB model imports
- Animated water shaders
- WebGPU renderer

## Capabilities

### New Capabilities
- None. This is a rendering re-implementation — no new external-facing behavior.

### Modified Capabilities
- `architecture`: R2 changes from "5 Canvas 2D skeleton files in `src/lib/canvas/`" to "7 Threlte components in `src/lib/canvas3d/` + Threlte Canvas mount"

## Approach

Replace the custom Canvas 2D engine loop (`Engine`, `Entities`, `Grid`, `Camera`) with Threlte 8's declarative Svelte 5 component tree. Three.js WebGLRenderer handles rendering; `OrbitControls` provides camera interaction. Delta snapshots from `simulationStore` feed reactive Svelte props into 3D components. The Threlte `<Canvas>` fills its parent container; existing Svelte panels (HUD, AgentInspector, ColonyInfo, EventLog, MetricChart) overlay via CSS positioning — no layout changes.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/lib/canvas/` | Removed | entities.ts, grid.ts, camera.ts, engine.ts, animation.ts |
| `src/lib/canvas3d/` | New | 7 components + store |
| `src/lib/components/SimCanvas.svelte` | Modified | Replace Engine instantiation with Threlte Canvas |
| `frontend/package.json` | Modified | Add @threlte/core, @threlte/extras, three |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Bundle size +~150 KB gzip | High | Code-split Threlte; lazy-load via `mount()` |
| Browser GPU incompatibility | Low | Three.js WebGL2 fallback is robust |
| Overengineering 2D sim in 3D | Med | Flat grid, basic geometries, no shadows for MVP |

## Rollback Plan

Revert `SimCanvas.svelte` to Engine import, restore `src/lib/canvas/` from git, remove `canvas3d/` directory and Threlte/Three.js deps from `package.json`.

## Success Criteria

- [ ] All agents render as colored spheres with role colors + faction borders
- [ ] Grid tiles render with resource geometries (cones for trees, boxes for stone, planes for terrain)
- [ ] OrbitControls: pan, rotate, zoom — camera is free 3D
- [ ] Agent click via raycasting sets `uiStore.selectedAgentId`
- [ ] Water tiles render as semi-transparent planes
- [ ] Selected agent shows a ring highlight
- [ ] All existing panel components render correctly over 3D canvas
