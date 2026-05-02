# Design: Graphical Overhaul Phase 2

## Technical Approach

Four disjoint features added to the existing Threlte 8 scene: (1) bloom post-processing via EffectComposer overriding Threlte's render, (2) ambient dust particles as a single THREE.Points, (3) harvest burst particles via tile-amount diffing, (4) agent idle bob via onBeforeCompile vertex injection. Zero new dependencies — all Three.js built-in.

## Architecture Decisions

### G8: Bloom — EffectComposer integration with Threlte 8

| Option | Tradeoff | Decision |
|--------|----------|----------|
| useTask + composer.render() after Threlte render | Double-renders scene (first Threlte, then composer), but OutputPass overwrites screen | **Chosen** — minimal code, composer OutputPass guarantees bloomed result |
| Disable Threlte render + manual composer | Clean single render, but requires hacking Threlte internals to suppress default render task | Rejected — fragile across Threlte upgrades |
| Custom post-processing shader in onBeforeCompile | No double render, but no selective bloom (glows everything) | Rejected — UnrealBloomPass is the standard for emissive-only bloom |

**Rationale**: Double-rendering the scene is imperceptible at this geometry complexity (instanced flat tiles + ~30 meshes). The OutputPass at the end of the composer chain renders to screen, overwriting Threlte's direct render. Simple, correct, upgrade-safe.

### G9: Ambient Particles — single Points draw call

**Choice**: A single `THREE.Points` with `PointsMaterial` (additive blending, depthWrite=false) updated per frame via `useTask` on the position BufferAttribute.

**Alternatives**: Per-particle meshes (300+ draw calls), sprite particles (texture load, larger batch). Rejected for performance.

**Rationale**: All particles share appearance — one draw call, one material. CPU cost is updating a Float32Array of positions (no object creation per frame). Sinusoidal motion in JS, not shader, to avoid custom ShaderMaterial + uniform boilerplate for such a simple effect.

### G10: Harvest Bursts — timer-driven Points per burst

**Choice**: On diff detection, spawn a new `THREE.Points` with 15 particles at the tile position. Each burst runs its own animation timeline via `useTask` — scale & opacity lerp to zero over 500ms, then remove.

**Alternatives**: Single pooled particle system (complex state machine, harder to time individual bursts), per-particle sprites (more setup). Rejected.

**Rationale**: Each burst is a tiny ephemeral object with its own lifecycle. Creating 15-point meshes is trivially cheap — worst case of 10 simultaneous bursts = 150 particles + 10 draw calls, still below threshold.

### G11: Agent Idle Bob — onBeforeCompile vertex displacement

**Choice**: Inject `sin(uTime * 3.0 + instanceOffset) * 0.03` into the agent material's vertex shader via `onBeforeCompile`. Use the existing `onBeforeCompile` hook already present for Fresnel.

**Alternatives**: Separate ShaderMaterial (loses MeshStandardMaterial base, needs custom lighting), JS-driven position update (CPU cost per agent). Rejected.

**Rationale**: The Fresnel `onBeforeCompile` already patches both vertex and fragment shaders — adding a vertex displacement there is zero additional overhead. GPU-driven, zero CPU cost per frame.

## Data Flow

```
  simulationStore snapshot (Svelte writable)
       │
       ├──→ Resources3D: $effect diffs resource amounts
       │      └── prevAmounts Map → {amount decreased} → spawnBurst(x, y, type)
       │
       ├──→ Scene: useTask → composer.render() [after Threlte default render]
       │      └── RenderPass → UnrealBloomPass → OutputPass → screen
       │
       ├──→ AmbientParticles: useTask → update position buffer (sinusoidal drift)
       │
       └──→ Agents3D: onBeforeCompile injects vertex displacement (uTime + per-instance phase)
              └── Already patched for Fresnel — appends bob to same hook
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/lib/canvas3d/Scene.svelte` | Modify | Add EffectComposer setup + useTask that calls composer.render() |
| `frontend/src/lib/canvas3d/AmbientParticles.svelte` | Create | 300-particle dust mote system, useTask-driven position animation |
| `frontend/src/lib/canvas3d/HarvestEffect.svelte` | Create | Ephemeral particle burst: spawn → fade → remove in 0.5s |
| `frontend/src/lib/canvas3d/Resources3D.svelte` | Modify | Add tile amount diff detection, burst triggering |
| `frontend/src/lib/canvas3d/Agents3D.svelte` | Modify | Add `sin(uTime * 3.0 + instanceOffset)` vertex displacement to existing Fresnel onBeforeCompile |
| `frontend/src/lib/components/SimCanvas.svelte` | Modify | Import and mount AmbientParticles, pass needed data |

## Interfaces / Contracts

### Harvest burst colors

```typescript
const BURST_COLORS: Record<string, string> = {
  berries: '#e53935',
  tree: '#5d4037',
  stone: '#9E9E9E',
  iron_ore: '#616161',
  clay: '#8d6e63',
  sand: '#fdd835',
  fiber: '#66bb6a'
};
```

### Bloom toggle uniform

```typescript
// Exposed on Scene component as prop or store value
let bloomEnabled = $state(true); // when false: bloomPass.strength = 0
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Visual | Bloom renders emissive elements with glow | Manual inspection — no frontend test framework available |
| Visual | Particles float gently | Manual — verify single Points mesh, count positions |
| Script | Harvest diff triggers burst | Unit-test the diff logic (pure function: prevAmounts → current → boolean) |
| Visual | Agent bob displacement | Manual — verify vertex position changes with onBeforeCompile |

## Open Questions

- [ ] None — all decisions documented and aligned with specs.
