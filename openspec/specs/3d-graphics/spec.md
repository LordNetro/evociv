# 3D Graphics Specification

## Purpose

Custom ShaderMaterial effects, InstancedMesh consolidation, and scene atmosphere for visual overhaul Phase 1. Replaces CPU-driven animations and per-instance stock materials with GPU-driven shaders and shared materials.

## Requirements

### Requirement: G1 — Water Shader

The system SHOULD use a custom ShaderMaterial for the water plane with vertex displacement, scrolling UV, and Fresnel rim glow.

#### Scenario: Animated wave displacement

- GIVEN a ShaderMaterial assigned to the water PlaneGeometry
- WHEN the vertex shader runs each frame
- THEN vertices displace by a sinusoidal wave function
- AND wave speed, amplitude, and frequency are configurable via uniforms

#### Scenario: Scrolling UV reflection

- GIVEN the water fragment shader samples UV coordinates
- WHEN the time uniform advances
- THEN UVs scroll with a uniform-driven offset
- AND the result produces a pseudo-reflection effect

#### Scenario: Fresnel rim glow

- GIVEN the water fragment shader evaluates the view angle
- WHEN a fragment is near grazing angle
- THEN a blue-white rim glow is blended onto the surface
- AND rim intensity attenuates toward normal-facing fragments

### Requirement: G2 — Selection Glow Shader

The system SHOULD use a GPU-driven pulse shader for the selection ring, replacing the CPU `useTask` animation loop.

#### Scenario: GPU pulse replaces useTask

- GIVEN a ShaderMaterial on the RingGeometry
- WHEN the time uniform advances each frame in the shader
- THEN ring emissive intensity pulses via GPU math
- AND no `useTask` or CPU timer drives the animation

#### Scenario: Configurable glow color

- GIVEN the selection glow uniforms `uColor` and `uIntensity`
- WHEN the selection color changes
- THEN the ring renders with the configured emissive color
- AND intensity is controlled by the uniform, not a CPU delta loop

### Requirement: G3 — Fog and Tone Mapping

The renderer MUST use ACESFilmic tone mapping. The scene MUST use FogExp2 for atmospheric depth.

#### Scenario: FogExp2 on scene

- GIVEN a scene reference
- WHEN FogExp2 is assigned to `scene.fog`
- THEN distant objects fade into the fog color
- AND fog density is configurable via the FogExp2 constructor

#### Scenario: ACESFilmic tone mapping

- GIVEN a WebGLRenderer instance
- WHEN `toneMapping` is set to `ACESFilmicToneMapping`
- THEN the renderer applies filmic tone mapping to all output
- AND `toneMappingExposure` is exposed as a configurable parameter

### Requirement: G4 — Grid Shading

The system SHOULD use a custom ShaderMaterial on the grid InstancedMesh with vertex height variation and anti-aliased grid lines.

#### Scenario: Vertex height variation

- GIVEN a ShaderMaterial on the grid InstancedMesh
- WHEN the vertex shader processes each instance
- THEN vertices displace subtly based on world position
- AND height variation creates non-flat terrain appearance

#### Scenario: Anti-aliased grid lines

- GIVEN the grid fragment shader samples fragment coordinates
- WHEN a fragment is near a grid line position
- THEN a grid line renders with smoothstep anti-aliased edges
- AND line spacing and thickness are controlled via uniforms

### Requirement: G5 — Agent Shared Materials

The system MUST reuse one MeshStandardMaterial per agent role color instead of creating per-agent materials. The system SHOULD add Fresnel rim glow via `onBeforeCompile`.

#### Scenario: Shared material per role

- GIVEN N agents with the same role
- WHEN their meshes are created
- THEN all share one MeshStandardMaterial instance keyed by role
- AND per-agent materials are NOT created

#### Scenario: Fresnel rim on agents

- GIVEN a MeshStandardMaterial with `onBeforeCompile` hook
- WHEN the shader compiles
- THEN a Fresnel rim edge glow is injected into the fragment shader
- AND rim color and strength are configurable

#### Scenario: Click interaction preserved

- GIVEN an agent mesh using a shared material
- WHEN the `oncreate` callback fires
- THEN the mesh is registered via `addInteractiveObject(ref)`
- AND the `onclick` handler still calls `uiStore.selectAgent(agentId)` (unchanged)

### Requirement: G6 — Tree Sway

The system SHOULD use vertex shader displacement for tree canopy sway, with pivot-at-base falloff.

#### Scenario: Sinusoidal canopy sway

- GIVEN a ShaderMaterial on tree canopy geometry
- WHEN the vertex shader runs
- THEN canopy vertices displace by a sinusoidal wave
- AND displacement amplitude increases with distance from tree base

#### Scenario: Wind uniform control

- GIVEN `uWindStrength` and `uWindFrequency` uniforms
- WHEN uniform values change
- THEN sway amplitude and speed respond accordingly
- AND no CPU animation loop drives the sway

### Requirement: G7 — Resource Instancing

The system MUST replace individual resource meshes with InstancedMesh per resource type. The system MUST add rendering support for `iron_ore`, `clay`, `sand`, and `fiber`.

#### Scenario: InstancedMesh per resource type

- GIVEN resources grouped by type (tree, berries, stone, iron_ore, clay, sand, fiber)
- WHEN the scene initializes
- THEN each type uses a single InstancedMesh with per-instance position and color attributes
- AND individual `<T.Mesh>` per-resource elements are removed

#### Scenario: New resource types render

- GIVEN resource types `iron_ore`, `clay`, `sand`, `fiber` in simulation state
- WHEN the scene renders
- THEN each renders with distinct geometry and material via InstancedMesh
- AND positions reflect simulation coordinates

#### Scenario: Simulation unchanged

- GIVEN the existing resource simulation logic
- WHEN InstancedMesh replaces individual meshes
- THEN resource count, positions, and spawning logic remain unchanged
- AND only the rendering layer is affected

#### Scenario: Click detection on instanced resources

- GIVEN an InstancedMesh with resource instances
- WHEN the user clicks a rendered instance
- THEN raycasting resolves the instanceId
- AND the corresponding resource data is retrievable via instanceId mapping
