# Design: 2D Sprite Rendering

## Technical Approach

Replace Threlte 8 + Three.js (15 files, 8 GLSL shaders, ~600KB+) with PixiJS v8 2D rendering. Mount a PixiJS `Application` imperatively inside a Svelte 5 component (`Canvas2D.svelte`). Three-container display list: World (tiles/resources/agents/structures), Effects (particles + day/night filter), Overlay (selection highlight + DOM label anchor). Port the `canvas3dStore` interpolation pattern to a plain TS class driven by PixiJS `Ticker`. DOM labels sync via `container.toGlobal()` each `requestAnimationFrame`. Procedural sprites via `PIXI.Graphics` + `RenderTexture` for MVP — no external assets.

## Architecture Decisions

### Decision: PixiJS v8 over Three.js

| Option | Bundle | GLSL? | Sprite batching | Effort |
|--------|--------|-------|-----------------|--------|
| Three.js (current) | ~600KB gzipped | Yes (8 shaders) | InstancedMesh | N/A |
| **PixiJS v8** | ~500KB gzipped | No | Auto (sprites) | Medium |
| Canvas 2D API | 0KB | No | None | High |

**Choice**: PixiJS v8. **Rationale**: No GLSL needed for 2D, auto sprite batching handles 2500 tiles in one draw call, mature filter system (ColorMatrixFilter for day/night), pixi-viewport for camera with zero extra effort.

### Decision: Plain TS Store over Svelte $state

**Choice**: `canvas2dStore` is a plain TypeScript class (no `$state` runes). **Rationale**: The store is mutated inside a PixiJS `Ticker` callback at 60fps. Svelte `$state` tracks every write — 60fps mutations into a reactive graph would trigger cascading updates in every `$derived`/`$effect` watching those properties. Plain TS keeps the hot path outside Svelte's reactivity.

### Decision: Imperative PixiJS, declarative Svelte

**Choice**: Create PixiJS objects imperatively in `onMount`, destroy in `onDestroy`. Use `$effect` to push state changes from Svelte stores into PixiJS objects. **Rationale**: PixiJS is an imperative API — trying to wrap sprites in Svelte components adds overhead. The container hierarchy is created once; reactive `$effect` blocks handle data updates (new tiles, agent moves, particle spawns).

### Decision: RAF for label sync, Ticker for animation

| Concern | Mechanism | Why |
|---------|-----------|-----|
| Agent interpolation | PixiJS Ticker | Must run in lockstep with render |
| DOM label positioning | requestAnimationFrame | No reason to update DOM mid-frame; avoids jitter from Ticker phases |
| Dialogue bubble expiry | Ticker (in store) | Must match agent interpolation timing |

## Data Flow

```
Backend ──WebSocket──→ simulationStore (writable)
                              │
                    $derived in Canvas2D.svelte
                              │
                    canvas2dStore.updateTargets()  ← $effect
                              │
                    PixiJS Ticker.tick(delta)
                     ├─ interpolate agent positions
                     ├─ animate particles
                     └─ expire dialogue bubbles
                              │
                    update sprite positions on World container
                              │
                    RAF: LabelSync → container.toGlobal()
```

## Container Hierarchy

```
Application.stage
├── World Container (z=0)
│   ├── TileGrid — PIXI.Sprite per tile (procedural atlas)
│   ├── ResourceOverlay — sprites for each resource (iron_ore icon, tree icon, etc.)
│   ├── Structures — sprites for buildings/walls
│   └── Agents — PIXI.Sprite per agent, tinted by faction color
│
├── Effects Container (z=1)
│   ├── HarvestParticles — @pixi/particle-emitter bursts
│   ├── AmbientParticles — floating dust (ParticleContainer)
│   ├── WeatherParticles — rain/snow (ParticleContainer)
│   └── DayNightFilter — PIXI.ColorMatrixFilter on this container
│
└── Overlay Container (z=2)
    ├── SelectionHighlight — animated ring sprite
    └── (anchor point for DOM labels — no sprites here)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/lib/canvas2d/Canvas2D.svelte` | Create | Root component. Mounts PixiJS + pixi-viewport. Hosts all 3 containers. |
| `frontend/src/lib/canvas2d/canvas2dStore.ts` | Create | Plain TS class: `agentPositions`, `targetPositions`, `lerpFactor`, `dialogueBubbles`. Methods: `updateTargets()`, `tick(delta)`. |
| `frontend/src/lib/canvas2d/TileGrid.ts` | Create | Generates procedural tile atlas via `PIXI.Graphics` + `RenderTexture`. Manages tile+resource sprites in World container. |
| `frontend/src/lib/canvas2d/AgentSprites.ts` | Create | Creates/recycles agent sprites. Applies faction tint via `sprite.tint`. Click handler → `uiStore.selectAgent()`. Reads interpolated positions from store. |
| `frontend/src/lib/canvas2d/EffectsLayer.ts` | Create | Manages Effects container: harvest emitter instances, ambientParticleContainer, weatherParticleContainer. |
| `frontend/src/lib/canvas2d/OverlayLayer.ts` | Create | Selection highlight ring (animated PIXI.Graphics). |
| `frontend/src/lib/canvas2d/LabelSync.ts` | Create | RAF loop: iterates agents, calls `worldContainer.toGlobal(pos)`, sets DOM element `style.transform`. |
| `frontend/src/lib/canvas2d/DayNightFilter.ts` | Create | Applies `PIXI.ColorMatrixFilter` to Effects container. Tween brightness/blue-shift based on daytime [0-1]. |
| `frontend/src/lib/canvas2d/CameraControls.ts` | Create | Configures pixi-viewport (drag pan, scroll zoom, clamp to grid). Keyboard pan. |
| `frontend/src/lib/components/SimCanvas.svelte` | Modify | Replace all canvas3d imports with `import Canvas2D from '$lib/canvas2d/Canvas2D.svelte'`. Remove `handleHarvest` (now internal to effects). |
| `frontend/package.json` | Modify | Remove: `@threlte/core`, `@threlte/extras`, `three`, `@types/three`. Add: `pixi.js` ^8.x, `pixi-viewport`, `@pixi/particle-emitter`. |
| `frontend/src/lib/canvas3d/` (15 files) | Delete | Entire directory. |
| `frontend/src/lib/shaders/` (8 files) | Delete | Entire directory. |

## Interfaces / Contracts

```typescript
// canvas2dStore.ts
interface AgentPos { x: number; y: number }
interface DialogueBubble {
  text: string; type: 'speech' | 'thought'; visibleUntil: number
}

class Canvas2DStore {
  agentPositions: Record<string, AgentPos>
  targetPositions: Record<string, AgentPos>
  lerpFactor: number
  dialogueBubbles: Record<string, DialogueBubble | null>
  updateTargets(snapshot: Snapshot): void   // called from $effect
  tick(delta: number): void                  // called from Ticker
}
```

```typescript
// Container labels
interface LabelElement {
  agentId: string; el: HTMLElement
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | canvas2dStore interpolation | Pure TS — test `tick()` produces correct lerped positions |
| Unit | TileGrid procedural atlas | Verify PIXI.RenderTexture is created + tile sprites have correct positions |
| Unit | DayNightFilter math | Test ColorMatrix coefficients for daytime 0, 0.5, 1.0 |
| Integration | Canvas2D mount/unmount | Mount Svelte component, verify PIXI.Application exists, destroy verifies cleanup |
| Integration | Agent click → selection | Simulate PIXI.FederatedPointerEvent on agent sprite, verify uiStore.selectedAgentId |
| E2E | Full render loop | (Manual) Run simulation, verify 60fps with 2500 tiles + 100 agents |

## Migration / Rollout

No migration required. The `canvas3d/` directory stays intact during development — switch a single import in `+page.svelte` to toggle between 3D and 2D. Delete 3D files only after 2D passes acceptance criteria.

## Open Questions

- [ ] pixi-viewport v8 compatibility with PixiJS v8 — verify on install, fallback: custom camera via `Container.scale`/`position` + `wheel`/`pointermove` events
- [ ] Procedural sprite quality — `PIXI.Graphics` icons may look basic; acceptable for MVP but need a Tileset decision milestone
- [ ] Weather particle density — `ParticleContainer` max count for 60fps on integrated GPUs
