# Delta for 3d-graphics

## ADDED Requirements

### Requirement: G8 — Post-Processing Bloom

The system MUST add bloom post-processing via EffectComposer with RenderPass + UnrealBloomPass + OutputPass. Bloom strength SHOULD be 0.3, radius 0.5, threshold 0.8 so only emissive/specular elements glow. Bloom MUST be togglable via a uniform for performance-sensitive contexts. The composited pipeline MUST integrate with Threlte 8's render loop via `useTask`.

#### Scenario: Render chain processes scene

- GIVEN an EffectComposer with RenderPass + UnrealBloomPass (strength 0.3, radius 0.5, threshold 0.8) + OutputPass
- WHEN the Threlte render loop runs via `useTask`
- THEN the composer renders the scene instead of the default WebGLRenderer
- AND emissive surfaces bloom subtly while diffuse surfaces are unaffected

#### Scenario: Bloom toggle via uniform

- GIVEN the bloom enabled uniform is set to `false`
- WHEN the composer renders the scene
- THEN the UnrealBloomPass is effectively bypassed (strength clamped to 0)
- AND the scene renders without bloom overhead

### Requirement: G9 — Ambient Particle System

The system SHOULD render floating dust motes using `THREE.Points` with `PointsMaterial`. Particle count SHOULD be 200–500, with small size (~0.02 units) and subtle opacity (~0.3). Gentle floating motion MUST be driven by a `useTask` that updates the position attribute each frame rather than per-particle transforms. Particles MUST distribute across the visible world area at various heights.

#### Scenario: Dust motes float gently

- GIVEN a `THREE.Points` instance with 300 particles and a `PointsMaterial` (size 0.02, opacity 0.3, transparent)
- WHEN `useTask` updates the `position` attribute each frame
- THEN particles drift in a slow sinusoidal pattern
- AND the motion is single-draw-call (one Points mesh, no per-particle transforms)

#### Scenario: Particles span world area

- GIVEN the visible world area bounds
- WHEN particles are initialized
- THEN positions spread uniformly within the bounds
- AND heights vary to create depth layering

### Requirement: G10 — Harvest Feedback Effects

The system MUST emit a short-lived particle burst when a resource tile amount decreases. Burst color MUST match the resource type (green for berries, brown for trees, gray for stone, etc.). Burst particles MUST fade to transparent and shrink over ~0.5 seconds, then be removed. Detection MUST use a tile diff comparison on `simulationStore` state.

#### Scenario: Resource harvested fires burst

- GIVEN a resource tile amount decreases between simulation ticks
- WHEN the tile diff is detected via `simulationStore` subscription
- THEN a particle burst spawns at the tile's world position
- AND burst color matches the resource palette (e.g., green for berries, brown for trees, gray for stone, red for iron, tan for clay, yellow for sand, beige for fiber)

#### Scenario: Burst lifecycle

- GIVEN a spawned harvest burst
- WHEN 0.5 seconds have elapsed
- THEN particles have faded to zero opacity and zero scale
- AND the particle system is removed from the scene

#### Scenario: No burst on unchanged tile

- GIVEN a resource tile whose amount has NOT changed
- WHEN the simulationStore diff is computed
- THEN no particle burst is spawned

### Requirement: G11 — Agent Idle Bob (Optional Stretch)

The system MAY add gentle floating motion to idle agents via vertex shader displacement. Amplitude SHOULD be ~0.05 units, frequency ~0.5 Hz. Each agent SHOULD use a different phase offset via instance attribute to avoid synchronous bobbing. The animation MUST be GPU-driven with zero CPU cost — no `useTask` or JS timer.

#### Scenario: Gentle vertex shader bob

- GIVEN an agent mesh with a ShaderMaterial that includes vertex displacement
- WHEN the vertex shader evaluates `sin(uTime * frequency + instancePhase) * amplitude`
- THEN the agent translates up and down by ~0.05 units at ~0.5 Hz
- AND no JavaScript animation loop drives the motion

#### Scenario: Per-agent phase offset

- GIVEN multiple agent instances
- WHEN each instance has a unique phase attribute
- THEN agents bob at the same frequency but visually out of sync
- AND the phase is set once at instance creation and never updated

