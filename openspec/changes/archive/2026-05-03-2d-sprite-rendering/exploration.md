## Exploration: 2D Sprite Rendering Redesign

### Current State

The frontend renders a **3D perspective view** of the simulation using **Threlte 8** (Svelte bindings for Three.js). The rendering system is spread across **15 files** in `frontend/src/lib/canvas3d/`:

| File | Purpose | Key Technology |
|------|---------|---------------|
| `Scene.svelte` | Root Threlte `<Canvas>` wrapper | Custom WebGLRenderer, ACESFilmic tone mapping |
| `SceneContent.svelte` | Camera + lighting setup | PerspectiveCamera (50° FOV), OrbitControls, 3 lights |
| `Grid3D.svelte` | Tile grid (InstancedMesh, 2500 tiles) | Custom ShaderMaterial (vertex height, grid lines) |
| `Resources3D.svelte` | 8 resource types as 3D shapes | InstancedMesh per type, custom tree sway shader |
| `WaterPlane.svelte` | Animated water surface | ShaderMaterial (wave displacement, Fresnel) |
| `Agents3D.svelte` | Agent spheres with role colors | Shared MeshStandardMaterial, Fresnel glow, bob anim |
| `AgentLabel.svelte` | HTML overlay labels + speech bubbles | @threlte/extras `<HTML>` component |
| `SelectionHighlight.svelte` | Pulse ring on selected agent | ShaderMaterial with GPU pulse |
| `HarvestEffect.svelte` | Ephemeral particle burst on harvest | THREE.Points, 15 particles, 500ms lifecycle |
| `AmbientParticles.svelte` | Floating dust motes | THREE.Points, 300 particles, sinusoidal drift |
| `PostProcessing.svelte` | Bloom effect | EffectComposer + UnrealBloomPass |
| `InteractivityInit.svelte` | Click/interaction setup + fog | Threlte interactivity plugin, FogExp2 |
| `KeyboardPan.svelte` | WASD + right-click camera | Direct OrbitControls manipulation |
| `canvas3dStore.svelte.ts` | Agent position interpolation + dialogue | State class with $state runes + tick() |
| `controlsStore.ts` | OrbitControls reference | Module-level ref |

**Data Flow:**
1. Backend → WebSocket → `simulationStore` (Svelte `writable`)
2. `SimCanvas.svelte` derives reactive data from the store (`$derived`)
3. Passes tiles, agents, factions as props to 3D components
4. `Agents3D.svelte` uses `$effect` to push snapshot positions to `canvas3dStore.updateTargets()`
5. `useTask` (Threlte's render-loop hook) drives `canvas3dStore.tick(delta)` for smooth interpolation
6. Post-processing (bloom) runs after Threlte's default render via `EffectComposer`

**Key characteristics:**
- **Grid**: 50×50 (2500 tiles max) — tiles with resources only are sent (delta snapshots)
- **Agents**: Variable count, potentially hundreds, rendered as colored spheres
- **View**: Perspective top-down (camera at [35, 30, 35], FOV 50°, looking at [25, 0, 25])
- **Performance**: InstancedMesh for tiles + resources, shared materials for agents
- **Dependencies**: `@threlte/core@^8.5.10`, `@threlte/extras@^9.15.0`, `three@^0.184.0` — all ~600KB+ gzipped bundled
- **Not yet rendered**: Structures (data model has them, frontend doesn't render them yet)

**Backend data model** (Pydantic `WorldSnapshot` sent via WebSocket):
- `tiles[]`: x, y, resource_type, amount, subtype
- `agents{}`: id → full state (position, role, faction, inventory, emotions, etc.)
- `structures[]`: id, structure_type, position, health, owner
- `factions[]`: id, name, color, member_count
- `time_state`: is_night, day_count, time_of_day_label
- `weather_state`: temperature, precipitation
- `faction_tile_visibility`: fog-of-war per faction

---

### Affected Areas

- **`frontend/src/lib/canvas3d/`** — ALL 15 files (will be deleted entirely and replaced by 2D system)
- **`frontend/src/lib/shaders/`** — 8 GLSL shader files (will be deleted — no GLSL needed for 2D)
- **`frontend/src/lib/components/SimCanvas.svelte`** — Major rewrite: switch from `<Scene>` to `<Canvas2D>`
- **`frontend/src/lib/stores/canvas3dStore.svelte.ts`** — Will be replaced/migrated (interpolation logic)
- **`frontend/src/lib/stores/controlsStore.ts`** — Will be deleted (OrbitControls → 2D camera)
- **`frontend/package.json`** — Remove `@threlte/core`, `@threlte/extras`, `three`, `@types/three`; add `pixi.js` and optionally plugins
- **`frontend/src/routes/+page.svelte`** — Minor: remove shader imports if any
- **`openspec/specs/3d-graphics/spec.md`** — Will be replaced by 2D rendering spec
- **`openspec/specs/3d-rendering/spec.md`** — Will be replaced
- **`openspec/config.yaml`** — Update tech stack description

---

### Approaches

#### 1. **PixiJS v8** — Full-featured 2D WebGL renderer
   PixiJS is a mature 2D rendering library that uses WebGL under the hood for hardware acceleration. It provides sprite batching, texture atlases, display list hierarchy, particle systems, filters/effects, and a ticker-based animation loop.

   - **Pros**:
     - Battle-tested, widely used in production web games
     - Automatic sprite batching for excellent performance (thousands of sprites in one draw call)
     - Built-in `Container` hierarchy for layering (map / agents / particles / UI overlays)
     - `TextureAtlas` / `Spritesheet` support for tilesets
     - `Ticker` for frame-rate-independent animations
     - `Graphics` API for procedural shapes (circles, rings, bars) — replaces 3D geometry
     - Rich filter system: `ColorMatrixFilter` (day/night tint), `BlurFilter`, `GlowFilter`
     - `@pixi/particle-emitter` plugin for particle effects
     - Plugin ecosystem: `pixi-viewport` for camera pan/zoom/drag
     - Clean embed in Svelte: mount `<canvas>` → `new Application({ view: canvas })`
   - **Cons**:
     - ~500KB gzipped bundle (but smaller than Three.js at ~600KB+ gzipped)
     - HTML/CSS overlay for labels needs separate DOM layer (like current AgentLabel approach)
     - No built-in 3D (irrelevant here)
     - Slightly different mental model from Three.js (2D display list vs 3D scene graph)
   - **Effort**: Medium
   - **Bundle impact**: ~500KB gzipped (PixiJS v8 core) — replaces Three.js' ~600KB+ gzipped, net ~same or less

#### 2. **HTML5 Canvas 2D API** — Native, zero dependencies
   Direct Canvas 2D context drawing with manual render loop (requestAnimationFrame).

   - **Pros**:
     - Zero dependencies — no bundle impact
     - Full control over every pixel
     - Canvas transforms (`translate`, `scale`, `rotate`) for camera
     - Compatible with any browser
     - `OffscreenCanvas` for worker-based rendering
   - **Cons**:
     - No sprite batching — each draw call is per-object (slow with 2500+ tiles)
     - Must implement from scratch: camera, tile map rendering, sprite animations, particles, z-ordering
     - No built-in texture atlas support
     - No particle system — need to write from scratch
     - No hit-testing / click detection — need manual coordinate math
     - Performance degrades significantly with many objects; ~1000 sprites is often the limit before jank
   - **Effort**: High
   - **Bundle impact**: Zero

#### 3. **Excalibur.js** — Full 2D game engine
   Excalibur is a TypeScript 2D game engine with ECS architecture, built-in tilemaps, particles, camera, and animations.

   - **Pros**:
     - Built-in tile map support with `TileMap`
     - Camera with zoom/pan built-in
     - Particle system built-in
     - ECS architecture for entity management
     - Built-in collision detection (useful for click/hover)
     - Animation system built-in
   - **Cons**:
     - Full game engine (~300KB gzipped) — overkill for a simulation viewer
     - Opinionated game loop (update/render) — may conflict with Svelte reactivity
     - ECS adds complexity for simple rendering needs
     - Smaller community than PixiJS
     - Heavier integration effort with Svelte
   - **Effort**: Medium-High
   - **Bundle impact**: ~300KB gzipped

#### 4. **CSS + DOM Positioning** — Pure DOM overlay
   Render tiles and agents as `<div>` elements positioned with CSS transforms. Use CSS transitions for smooth movement.

   - **Pros**:
     - Zero additional dependencies
     - GPU-accelerated via CSS compositing
     - CSS transitions for smooth animations
     - Easy click handling (native DOM events)
     - Easy label/speech bubble rendering (HTML)
   - **Cons**:
     - HARD performance ceiling at ~200-300 DOM elements (2500 tiles is impossible)
     - No batching — every element is a DOM node
     - No particle effects (CSS can't do point clouds efficiently)
     - No z-ordering control beyond z-index
     - Camera zoom requires CSS `scale()` transforms which blur text/sprites
   - **Effort**: Low initially, High to scale
   - **Bundle impact**: Zero

---

### Recommendation

**Use PixiJS v8 as the 2D rendering core**, with the following specific strategy:

**Why PixiJS wins:**

1. **Performance parity with Three.js**: Both use WebGL. PixiJS replaces Three.js at the same layer but for 2D. The existing InstancedMesh pattern maps cleanly to PixiJS sprite batching.

2. **Tile batching**: PixiJS automatically batches sprites sharing the same texture. A 50×50 grid of floor tiles is ONE draw call with a texture atlas. The 8 resource types with varying amounts become ~8 draw calls.

3. **Particle support**: Both harvest burst effects (15 particles) and ambient dust (300 particles) are trivially handled by PixiJS `ParticleContainer` or `@pixi/particle-emitter`. No need to write custom BufferGeometry.

4. **Camera controls**: `pixi-viewport` plugin provides drag-to-pan, scroll-to-zoom, mouse-wheel, WASD, and edge-scrolling out of the box.

5. **Similar complexity to current system**: The PixiJS Application + Ticker replaces Threlte's Canvas + useTask. The mental model transition is manageable.

6. **Smaller than Three.js**: PixiJS v8 is ~500KB gzipped vs Three.js ~600KB+ — net bundle decrease.

**Rendering architecture recommendation:**

```
Container: World (map layer)
  ├── Tile sprites (grid background, colored by resource type)
  ├── Resource sprites (icons/shapes overlaid on tiles)
  ├── Structure sprites (buildings)
  └── Agent sprites (with smooth position interpolation)
Container: Effects (above map)
  ├── Harvest particle bursts
  ├── Ambient dust motes
  ├── Day/night overlay (tinted Graphics or ColorMatrixFilter)
  └── Weather overlay (rain/snow particles)
Container: Overlay (above effects)
  ├── Selection highlight (Graphics circle)
  ├── Agent labels + speech bubbles (DOM/CSS overlay layer)
  └── Fog-of-war (dark Graphics shapes or alpha mask)
```

**Animation strategy:**
- Reuse `canvas3dStore` pattern but adapt it: PixiJS `Ticker` callback replaces `useTask`
- `$effect` pushes new target positions → `Ticker` interpolates each frame
- Particle effects use PixiJS particle emitters with configurable lifetimes
- Day/night transition: tween `ColorMatrixFilter` brightness over time
- Weather overlay: particle emitter with rain/snow texture

**Sprite rendering (vs 3D primitives):**
- Instead of colored 3D spheres for agents, use a generated sprite texture (colored circle with faction ring) created via `Pixi.Graphics` → renderTexture
- Instead of 3D boxes for resources, use simple sprites or Graphics primitives
- Instead of custom ShaderMaterial for water, use animated tinted Graphics or animated sprite
- Instead of custom tree sway shader, use a sprite sway via position offset in Ticker

**Tile rendering (50×50 grid):**
- Use `PIXI.Graphics` or a generated texture for the grid background
- Use sprites for resource overlays on tiles
- Since the current system only renders tiles with resources, adopt the same approach: maintain a Map of tile sprites

**Click interaction:**
- PixiJS sprites are interactive by default (`.eventMode = 'static'`)
- Click on agent sprite → `uiStore.selectAgent(agentId)` — same as current
- Click on resource → could open info panel (same as current stub)

**Particle effects:**
- **Harvest bursts**: `@pixi/particle-emitter` with config — spawn 15 particles at position, animate over 500ms. Maps directly from current HarvestEffect.
- **Ambient particles**: `ParticleContainer` with 300 sprites, update positions in Ticker. Maps from current AmbientParticles.
- **Rain/snow**: Weather data from snapshot → toggle particle emitter on/off or change emission rate.

**Day/night and weather overlays:**
- Day/night from `time_state.is_night`: apply `ColorMatrixFilter` to the World Container (darken + desaturate) + overlay a dim dark-blue Graphics rectangle with opacity
- Weather from `weather_state.precipitation`: rain particle emitter

**Agent labels + dialogue:**
- Keep as DOM/CSS overlay (HTML `<div>` positioned over canvas) — same approach as current AgentLabel
- PixiJS renders to a `<canvas>` — position a separate DOM layer on top with `pointer-events: none`
- Sync positions from PixiJS world coords to screen coords each frame

**Data flow adaptation:**
```typescript
// simulationStore remains unchanged (Svelte writable)
// SimCanvas.svelte switches from:
<Scene>
  <Grid3D tiles={tiles} />
  <Agents3D agents={agents} factions={factions} />
  ...
</Scene>
// To:
<Canvas2D tiles={tiles} agents={agents} factions={factions} structures={structures}
          timeState={time_state} weatherState={weather_state} />
```

---

### Risks

1. **Removing Threlte/Three.js breaks existing 3D specs** — The specs in `openspec/specs/3d-graphics/` and `openspec/specs/3d-rendering/` are tightly coupled to Three.js features (custom shaders, InstancedMesh, bloom). A full spec rewrite is required. The `graphical-overhaul-phase2` change will also be superseded.

2. **pixi-viewport maturity** — `pixi-viewport` v8 compatibility with PixiJS v8 should be verified. If incompatible, need custom camera implementation.

3. **Svelte 5 + PixiJS reactivity** — PixiJS's imperative API and Svelte 5's reactive runes need careful bridging. Cannot use `$state` inside PixiJS objects. The existing pattern of a store + $effect pushing data into an imperative render loop is correct and should be preserved.

4. **Sprite asset pipeline** — The "C:DDA-style rich 2D tileset" requires a tile atlas. Need to decide: (a) generate sprites programmatically with PixiJS Graphics, (b) source an existing tileset, (c) create a simple procedural sprite system. Option (a) is fastest for prototyping. Option (b) is best for visual quality.

5. **Performance with 2500+ interactive sprites** — Each tile/agent being interactive adds event listeners. PixiJS batching helps, but hit-testing many sprites can be slow. Mitigation: only make agents interactive; use a single Graphics overlay for grid hit-testing or disable interactivity on non-interactive elements.

6. **Fog of war** — Currently planned in backend (`faction_tile_visibility`) but not implemented in rendering. The 2D system makes fog-of-war easier (a container with dark Graphics over undiscovered tiles), but it's additional complexity.

7. **Canvas-to-DOM coordinate sync** — Agent labels (HTML) need per-frame position sync from PixiJS world coords to screen coords. The current Threlte system used `@threlte/extras <HTML>` which handles this automatically. Need to implement `container.toGlobal()` + manual DOM positioning.

---

### Ready for Proposal
Yes
