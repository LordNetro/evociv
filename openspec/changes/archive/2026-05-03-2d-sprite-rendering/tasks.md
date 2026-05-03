# Tasks: 2D Sprite Rendering

## Phase 1: Infrastructure

- [x] 1.1 Update `package.json` — remove `three`, `@threlte/core`, `@threlte/extras`, `@types/three`; add `pixi.js` ^8.x, `pixi-viewport`, `@pixi/particle-emitter`
- [x] 1.2 Create `canvas2dStore.ts` — plain TS class porting interpolation logic from `canvas3dStore`; `updateTargets()`, `tick(delta)`, agent/dialogue state
- [x] 1.3 Create `CameraControls.ts` — configure pixi-viewport with drag pan, scroll zoom, keyboard pan, grid-edge clamping
- [x] 1.4 Create `Canvas2D.svelte` — mount PixiJS `Application` in `onMount`, 3-container display list (World/Effects/Overlay), destroy in `onDestroy`
- [x] 1.5 Test: `canvas2dStore.tick()` produces correct lerped positions from targets

## Phase 2: Core Rendering

- [x] 2.1 Create `TileGrid.ts` — procedural atlas via `PIXI.Graphics` + `RenderTexture`; 50×50 sprite grid + resource overlay sprites in World container
- [x] 2.2 Create `AgentSprites.ts` — recycle agent sprites, apply faction tint via `sprite.tint`, click handler → `uiStore.selectAgent()`
- [x] 2.3 Wire simulation → canvas2dStore — add `$effect` in `Canvas2D.svelte` feeding snapshots to `updateTargets()`, drive `tick()` from PixiJS `Ticker`
- [x] 2.4 Test: TileGrid creates `RenderTexture` and positions 2500 tile sprites correctly
- [x] 2.5 Test: Programmatic click on agent sprite calls `uiStore.selectAgent()` with correct ID

## Phase 3: Effects & Polish

- [x] 3.1 Create `EffectsLayer.ts` — harvest burst emitters, `ParticleContainer` for ambient dust and rain/snow
- [x] 3.2 Create `DayNightFilter.ts` — `PIXI.ColorMatrixFilter` on Effects container; tween brightness/blue-shift by simulation daytime value
- [x] 3.3 Create `OverlayLayer.ts` — animated selection highlight ring via `PIXI.Graphics` in Overlay container
- [x] 3.4 Create `LabelSync.ts` — RAF loop calling `worldContainer.toGlobal()` per agent, updating DOM element `style.transform`
- [x] 3.5 Test: DayNightFilter `ColorMatrix` coefficients produce correct tint at daytime 0, 0.5, 1.0

## Phase 4: Integration

- [x] 4.1 Rewrite `SimCanvas.svelte` — replace all `canvas3d/` imports with `import Canvas2D from '$lib/canvas2d/Canvas2D.svelte'`, wire `$derived` snapshots
- [x] 4.2 Remove `handleHarvest()` from `SimCanvas` — harvest particle spawn is now internal to `EffectsLayer`
- [x] 4.3 Integration test: Canvas2D module imports verify component + sub-modules available

## Phase 5: Cleanup & Archive

- [x] 5.1 Delete `frontend/src/lib/canvas3d/` (15 files) — no longer needed after 2D passes acceptance
- [x] 5.2 Delete `frontend/src/lib/shaders/` (8 GLSL files) — shaders not used by 2D pipeline
- [x] 5.3 Verify no orphaned imports — grep for `canvas3d`, `shaders`, `controlsStore` returns nothing
- [x] 5.4 Verify build succeeds — `npm run build` passes, `svelte-check` 0 errors, `lint` passes, `vitest run` 60/60 pass
