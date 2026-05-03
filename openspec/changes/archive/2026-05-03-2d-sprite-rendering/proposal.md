# Proposal: 2D Sprite Rendering

## Intent

Replace 3D rendering (Threlte 8 + Three.js) with 2D sprite-based rendering (PixiJS v8) inspired by Cataclysm:DDA. The 3D system — 15 files, 8 GLSL shaders, ~600KB+ gzipped — adds complexity a 2D top-down simulation doesn't need.

## Scope

### In Scope
- Delete `canvas3d/` (15 files) + `shaders/` (8 GLSL files)
- PixiJS v8 Application with 3-container hierarchy (World/Effects/Overlay)
- Sprite tile grid (50×50) with resource overlays
- Agent sprites (faction colors + smooth interpolation)
- Particles (harvest bursts, ambient dust, rain/snow)
- Camera pan/zoom via pixi-viewport
- Day/night ColorMatrixFilter + structure rendering
- DOM labels (agent names + speech bubbles)
- Rewrite SimCanvas.svelte → Canvas2D component
- Update package.json (remove three, add pixi.js)
- New `2d-rendering` spec (replaces `3d-graphics` + `3d-rendering`)

### Out of Scope
- Tileset art pipeline (procedural sprites for MVP)
- Fog of war (deferred to map-memory change)
- Backend changes (data model is already 2D-compatible)

## Capabilities

### New
- `2d-rendering`: 2D sprite rendering — tile grid, agents, particles, effects, camera. Replaces `3d-graphics` + `3d-rendering`.

### Modified
- `architecture`: Update tech stack (Three.js → PixiJS) + canvas skeleton references

## Approach

Mount PixiJS `Application` on a `<canvas>` in `<Canvas2D>`. Three containers: World (tiles/agents as batched sprites from procedural atlas), Effects (particles, day/night filter), Overlay (selection, DOM labels). Port `canvas3dStore` interpolation to PixiJS `Ticker`. `$effect` pushes data into PixiJS objects. DOM labels sync via `container.toGlobal()`. No external assets — sprites generated via `PIXI.Graphics` + `renderTexture`.

## Affected Areas

| Area | Change |
|------|--------|
| `frontend/src/lib/canvas3d/` (15 files) | Deleted |
| `frontend/src/lib/shaders/` (8 files) | Deleted |
| `canvas3dStore.svelte.ts` | → `canvas2dStore.ts` |
| `controlsStore.ts` | Deleted |
| `SimCanvas.svelte` | Rewritten: imports Canvas2D |
| `package.json` | 3 deps removed, 3 added |
| `3d-graphics/spec.md` | Deleted → `2d-rendering` |
| `3d-rendering/spec.md` | Deleted → `2d-rendering` |
| `architecture/spec.md` | Modified (tech stack) |
| `openspec/config.yaml` | Modified (context) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| pixi-viewport v8 incompatibility | Low | Custom camera via Container transform |
| Svelte ↔ PixiJS reactivity bridge | Low | Existing store pattern handles this |
| Label DOM jitter | Medium | RAF positioning, not Ticker |
| Procedural sprites look basic | Medium | Acceptable for MVP |

## Rollback Plan

Keep `canvas3d/` intact. If 2D fails: revert `package.json`, restore files, restore deleted specs.

## Dependencies

- `pixi.js` v8 (~500KB gzipped)
- `pixi-viewport`, `@pixi/particle-emitter`

## Success Criteria

- [ ] 50×50 grid at 60fps with resource overlays
- [ ] Agent sprites with faction colors + smooth movement
- [ ] Camera pan/zoom works
- [ ] Particles (harvest, ambient, rain) render
- [ ] Day/night filter tints scene
- [ ] Agent click opens AgentInspector
- [ ] Zero backend test regression
- [ ] Bundle ≤ current size
