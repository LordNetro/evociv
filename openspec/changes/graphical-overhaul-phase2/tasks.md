# Tasks: Graphical Overhaul Phase 2

## Phase 1: Bloom Post-Processing

- [x] 1.1 Add EffectComposer, RenderPass, UnrealBloomPass, OutputPass imports to `frontend/src/lib/canvas3d/Scene.svelte`
- [x] 1.2 Create composer chain with `useTask('render')` that calls `composer.render()` after Threlte's default render — bloom strength 0.3, radius 0.5, threshold 0.8, with toggle uniform (strength=0 when disabled) (Spec G8 Scenarios)
- [x] 1.3 Handle window resize via ResizeObserver to update composer size

## Phase 2: Ambient Particles

- [x] 2.1 Create `frontend/src/lib/canvas3d/AmbientParticles.svelte` — single THREE.Points with 300 dust motes (PointsMaterial, size 0.02, opacity 0.3), sinusoidal drift via useTask updating position BufferAttribute, distributed across world bounds with height variance (Spec G9 Scenarios)
- [x] 2.2 Mount `<AmbientParticles />` inside Canvas in `Scene.svelte` (before children slot)

## Phase 3: Harvest Feedback Effects

- [x] 3.1 Create `frontend/src/lib/canvas3d/HarvestEffect.svelte` — ephemeral THREE.Points burst (15 particles), color from resource palette (berries=#e53935, tree=#5d4037, stone=#9E9E9E, iron_ore=#616161, clay=#8d6e63, sand=#fdd835, fiber=#66bb6a), fade/scale to zero over 0.5s, then self-remove (Spec G10 Scenarios)
- [x] 3.2 Add tile-amount diff detection in `Resources3D.svelte` — $effect compares current vs previous resource amounts, triggers burst at tile world position on decrease
- [x] 3.3 Mount `HarvestEffect` in `SimCanvas.svelte` wired to diff events from Resources3D

## Phase 4: Agent Idle Bob

- [x] 4.1 Add per-instance phase attribute to agent instances in `Agents3D.svelte` for unique bob offset
- [x] 4.2 Inject `sin(uTime * 3.0 + instancePhase) * 0.03` vertex displacement into the existing Fresnel `onBeforeCompile` hook, add uTime uniform to shared material (Spec G11 Scenarios — GPU-driven, zero JS per frame)

## Phase 5: Verification

- [x] 5.1 `npm run build` — must pass with no errors
- [x] 5.2 `svelte-check` — 0 type errors
- [x] 5.3 Backend tests — 300 passing

