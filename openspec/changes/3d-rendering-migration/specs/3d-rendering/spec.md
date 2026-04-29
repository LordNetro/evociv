# Spec: 3d-rendering

## Capabilities

### capability: 3d-rendering
**Depends on**: simulation-engine

Replaces Canvas 2D rendering with Threlte 8 + Three.js WebGL for 3D scene graph, free camera, and extensible rendering.

#### Requirements

| # | Requirement | Strength |
|---|-------------|----------|
| 3D-R1 | The system MUST render the simulation via Threlte 8 `<Canvas>` with perspective camera, ambient + directional lights, and OrbitControls (pan, rotate, zoom). | MUST |
| 3D-R2 | Grid tiles MUST render as colored 3D planes matching current 2D colors: resource tiles `#3d2b1f`, empty tiles `#2d1b0e`. | MUST |
| 3D-R3 | Resources MUST render as 3D primitives on tile centers: trees = green cones (`#2e7d32`), berries = red spheres (`#c62828`), stone = gray boxes (`#757575`), water = semi-transparent blue planes (`rgba(21,101,192,0.6)`). | MUST |
| 3D-R4 | Agents MUST render as spheres colored by role (gatherer `#4CAF50`, builder `#FF9800`, scout `#2196F3`, warrior `#F44336`), elevated 0.5 units above their tile. Agents with a faction MUST display a faction-colored ring. Child agents MUST render at 60% scale. | MUST |
| 3D-R5 | Clicking an agent via raycasting MUST set `uiStore.selectedAgentId`. The selected agent MUST display a highlight ring. | MUST |
| 3D-R6 | Agent 3D positions SHOULD interpolate between tick updates using linear or eased interpolation for smooth movement. | SHOULD |
| 3D-R7 | Existing Svelte panels (HUD, AgentInspector, ColonyInfo, EventLog, MetricChart) MUST render over the 3D canvas via CSS positioning — no layout changes permitted. | MUST |
| 3D-R8 | The system MUST consume the same `simulationStore` as the 2D renderer. Zero backend changes are permitted — same WebSocket delta snapshots, same data shape. | MUST |
| 3D-R9 | The system MUST maintain ≤60fps on mid-range hardware (integrated GPU, 8GB RAM) with a 50×50 grid and ≥20 agents. | MUST |
| 3D-R10 | The five Canvas 2D files (`engine.ts`, `grid.ts`, `entities.ts`, `camera.ts`, `animation.ts`) MUST be removed. `SimCanvas.svelte` MUST mount the Threlte `<Canvas>` instead of the Engine class. | MUST |

#### Scenarios

- GIVEN the `<Canvas>` mounts with a 50×50 world WHEN rendered THEN a perspective camera, ambient light, directional light, and OrbitControls are active at ≥30fps
- GIVEN a tile at (5,5) with `resource_type="tree"` WHEN Grid3D renders THEN a green cone is centered on `(5, 0, 5)` above the tile plane
- GIVEN a gatherer with `faction_id="f1"` at (3,4) WHEN Agents3D renders THEN a `#4CAF50` sphere at `(3, 0.5, 4)` shows a faction-colored ring
- GIVEN a child agent WHEN rendered THEN its sphere radius is 60% of an adult agent's radius
- GIVEN the user clicks on an agent sphere WHEN the raycaster detects the hit THEN `uiStore.selectedAgentId` is set and a highlight ring appears
- GIVEN a tick updates agent position from (0,0) to (5,0) WHEN the position prop changes THEN the agent interpolates over ~200ms instead of snapping
- GIVEN SimCanvas mounts Threlte `<Canvas>` WHEN HUD and AgentInspector are present THEN panels render above the canvas with correct z-ordering
- GIVEN `simulationStore.updateFromSnapshot(data)` fires from WebSocket WHEN the store updates THEN 3D component props react via `$effect` / `$derived`
- GIVEN a 50×50 grid with 20 agents on integrated GPU at 1920×1080 WHEN rendering THEN frame rate ≥30fps (target ≤60fps, minimum 30fps)
- GIVEN the old `src/lib/canvas/` files exist BEFORE the change WHEN applied THEN all five files are removed and SimCanvas.svelte uses Threlte
