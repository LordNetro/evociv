# Delta for architecture

## MODIFIED Requirements

### R2: Canvas Engine Skeletons → Threlte 3D Components

The system MUST remove the five Canvas 2D skeleton TypeScript files from `frontend/src/lib/canvas/` and provide seven Threlte 8 components under `frontend/src/lib/canvas3d/`: `Scene.svelte`, `Agents3D.svelte`, `Grid3D.svelte`, `AgentLabel.svelte`, `WaterPlane.svelte`, `SelectionHighlight.svelte`, and a reactive `canvas3dStore.svelte.js`. The old `SimCanvas.svelte` MUST mount Threlte `<Canvas>` instead of the `Engine` class.

**Removed files**: `engine.ts`, `grid.ts`, `entities.ts`, `animation.ts`, `camera.ts`
**New files**: `Scene.svelte`, `Agents3D.svelte`, `Grid3D.svelte`, `AgentLabel.svelte`, `WaterPlane.svelte`, `SelectionHighlight.svelte`, `canvas3dStore.svelte.js`

(Previously: "five skeleton Canvas 2D files under frontend/src/lib/canvas/")

#### Scenario: New component tree mounts without errors

- GIVEN `frontend/package.json` includes `@threlte/core`, `@threlte/extras`, `three`
- WHEN `SimCanvas.svelte` mounts the Threlte `<Canvas>` with the 7 components
- THEN the scene renders with no runtime errors and the browser console shows no WebGL warnings

#### Scenario: Old canvas files removed

- GIVEN the project source tree
- WHEN listing `frontend/src/lib/canvas/`
- THEN the directory contains zero files (or does not exist)

#### Scenario: Backward-compatible data flow

- GIVEN a WebSocket delta snapshot is received
- WHEN `simulationStore.updateFromSnapshot(data)` fires
- THEN `Agents3D` and `Grid3D` reactively consume the store data via Svelte 5 `$effect`/`$derived` without type errors
