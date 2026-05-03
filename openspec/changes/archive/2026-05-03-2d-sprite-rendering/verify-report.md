## Verify: 2D Sprite Rendering

### Spec Compliance

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| R1 | Sprite Tile Grid | ✅ | 50×50 procedural atlas via PIXI.Graphics+RenderTexture, 2500 tile sprites in World container |
| R1a | Full grid at 60fps | ✅ | TileGrid.build() creates 2500 sprites, tested in TileGrid.test.ts |
| R1b | Resource overlay | ✅ | TileGrid.addResourceOverlay() works — tested with iron_ore, trees, water overlays |
| R2 | Agent Sprites | ✅ | Faction-tinted sprites with click→selectAgent, smooth interpolation |
| R2a | Faction color tint | ✅ | AgentSprites applies faction color via sprite.tint — tested |
| R2b | Smooth movement | ✅ | canvas2dStore.tick() lerps positions toward targets — fully tested |
| R3 | Particle Effects | ✅ | EffectsLayer with harvest bursts, ambient dust in Effects container |
| R3a | Harvest burst | ✅ | spawnHarvestBurst creates 15 particles with velocity, fade, and lifetime — tested |
| R3b | Rain particles | ✅ | setWeather(true, 'rain') creates 500 weather particles with fall behavior |
| R4 | Camera Pan/Zoom | ✅ | pixi-viewport with drag, wheel, pinch, decelerate, clamp, clampZoom |
| R4a | Pan clamps to grid edge | ✅ | CameraControls uses viewport.clamp({direction:'all'}) — tested plugin config |
| R4b | Zoom preserves appearance | ✅ | viewport.clampZoom({minScale:0.3, maxScale:3.0}) — tested plugin config |
| R5 | Day/Night Filter | ✅ | PIXI.ColorMatrixFilter with cyclic tween — tested at daytime 0, 0.5, 1.0 |
| R5a | Night tint applied | ⚠️ Partial | Filter is applied to worldContainer, not effectsContainer as design specified. Production values correct: blue-shift + dark at daytime=0. |
| R6 | DOM Label Overlay | ⚠️ Partial | Agent name labels sync via RAF toGlobal(). Speech bubbles NOT rendered as DOM — only tracked in canvas2dStore data model. |
| R6a | Label follows agent | ✅ | LabelSync.sync() updates CSS transform via toGlobal() each RAF — tested |
| R6b | Speech bubble | ❌ Missing | canvas2dStore tracks dialogueBubbles with expiry but LabelSync does NOT render them as DOM speech bubbles above agents. No test exists. |

### Design Compliance

| Decision | Status | Notes |
|----------|--------|-------|
| PixiJS v8 over Three.js | ✅ | pixi.js ^8.18.1 in package.json. Three.js, @threlte/* removed. |
| Plain TS Store over Svelte $state | ✅ | canvas2dStore is a plain TS class — no $state runes. Wired via $effect in Canvas2D.svelte. |
| Imperative PixiJS, declarative Svelte | ✅ | PixiJS objects created in onMount, destroyed in onDestroy. $effect pushes data changes. |
| RAF for label sync, Ticker for animation | ✅ | LabelSync uses requestAnimationFrame. Agent interpolation + effects driven by PixiJS Ticker. |
| Container hierarchy: World → Effects → Overlay | ✅ | Three containers created in order: worldContainer (z=0), effectsContainer (z=1), overlayContainer (z=2) |
| World container inside viewport for camera | ✅ | TileGrid and AgentSprites added to viewport (worldContainer inside viewport) |
| DayNightFilter on Effects container | ⚠️ Deviatied | Applied to worldContainer instead. Effects (particles) won't get the day/night tint. |
| Procedural atlas via Graphics + RenderTexture | ✅ | TileGrid generates grass tile texture procedurally |
| simCanvas → Canvas2D import swap | ✅ | SimCanvas.svelte imports Canvas2D from $lib/canvas2d/Canvas2D.svelte |
| Remove canvas3d/ and shaders/ | ✅ | Both directories deleted, no orphaned imports confirmed |
| pixi-viewport v8 compatibility | ✅ | pixi-viewport ^6.0.3 with pixi.js ^8.18.1 — v6 targets PixiJS v8 |

### Task Completion

- **Phase 1 (Infrastructure)**: 5/5 completed
- **Phase 2 (Core Rendering)**: 5/5 completed
- **Phase 3 (Effects & Polish)**: 5/5 completed
- **Phase 4 (Integration)**: 3/3 completed
- **Phase 5 (Cleanup & Archive)**: 4/4 completed — **but** task 5.4 claims "svelte-check 0 errors" which is false

### Test Results

| Metric | Value |
|--------|-------|
| Total tests | 60 |
| Passing | 60 |
| Failing | 0 |
| Test files | 9 |

**Test distribution:**
- canvas2dStore.test.ts — 11 tests ✅
- TileGrid.test.ts — 6 tests ✅
- AgentSprites.test.ts — 7 tests ✅
- CameraControls.test.ts — 3 tests ✅
- DayNightFilter.test.ts — 7 tests ✅
- EffectsLayer.test.ts — 8 tests ✅
- OverlayLayer.test.ts — 8 tests ✅
- LabelSync.test.ts — 7 tests ✅
- Canvas2D.test.ts — 3 tests ✅

### Build Verification

| Command | Status | Details |
|---------|--------|---------|
| `npm run build` | ✅ Passes | vite build succeeds, SSR + client bundles generated |
| `npm run check` (svelte-check) | ❌ Fails | 9 type errors in Canvas2D.svelte |
| `npm run lint` | ✅ Passes | Prettier formatting OK, ESLint 0 errors |

**svelte-check errors (all in `Canvas2D.svelte`):**

| Line | Error |
|------|-------|
| 134 | `snapshot.agents` not assignable to `Record<string, AgentState>` |
| 147 | Property 'includes' does not exist on type `{}` |
| 148 | Property 'includes' does not exist on type `{}` |
| 149 | Property 'includes' does not exist on type `{}` |
| 154 | Property 'split' does not exist on type `{}` |
| 156 | Element implicitly has 'any' type — can't index `{}` with `0` |
| 156 | Element implicitly has 'any' type — can't index `{}` with `1` |
| 160 | `{} | null` not assignable to `string \| null` |
| 166 | `snapshot.agents` not assignable to parameter type |

**Root cause:** Line 127 casts `$simulationStore as Record<string, unknown>`, making all nested property accesses (`snapshot.agents`, `currentAction`, `pos`) typed as `unknown`. Every method call (`.includes()`, `.split()`, index access) on `unknown` is a type error.

### Overall Verdict

**CRITICAL**

### Issues

**CRITICAL (must fix before archive):**

1. **svelte-check: 9 type errors in Canvas2D.svelte** — Task 5.4 explicitly requires "svelte-check 0 errors". The `as Record<string, unknown>` cast causes all nested properties to be `unknown`. Fix: use the proper `SimulationState` type from simulationStore (defined via JSDoc) or cast with specific types for the sub-properties accessed.

2. **R6 Speech bubble not implemented** — The scenario requires "a DOM speech bubble renders above the agent sprite" when an agent has an active speech message. The `canvas2dStore.dialogueBubbles` data model supports this but `LabelSync` does not render speech/thought bubbles. Either LabelSync needs speech bubble rendering or a separate mechanism must be added.

**WARNING:**

3. **DayNightFilter applied to worldContainer, not effectsContainer** — Design specifies DayNightFilter on the Effects container, but the code applies it to `worldContainer` instead. This means particle effects won't get the day/night tint. Either the design should be updated or the code should move the filter.

**SUGGESTION:**

4. **Test coverage gap: weather particles** — `setWeather()` is tested only indirectly via `addChild` calls. No explicit tests verify rain particle positions, wrap-around behavior, or clearing on `setWeather(false)`.

5. **PIXI.ParticleContainer not used** — Design specifies `ParticleContainer` for GPU batching of ambient/weather particles, but the implementation uses plain `Container` with individual `Sprite` objects. For 300+800 particles this may impact performance. Worth benchmarking.
