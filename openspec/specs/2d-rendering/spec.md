# 2D Rendering Specification

## Purpose

2D sprite rendering for top-down simulation using PixiJS v8. Replaces the Three.js 3D stack. Provides tile grid, agent sprites, particle effects, camera control, day/night filter, and DOM label overlay.

## Requirements

### R1: Sprite Tile Grid

The system MUST render a 50×50 tile grid as batched sprites from a procedural atlas (PIXI.Graphics + renderTexture). Resource overlays MUST display above terrain tiles in the World container.

#### Scenario: Full grid at 60fps
- GIVEN 50×50 tiles initialized in the World container
- WHEN the render loop runs at 60fps
- THEN all 2500 tiles render without frame drops

#### Scenario: Resource overlay
- GIVEN a tile with resource type `iron_ore`
- WHEN the tile renders
- THEN a resource sprite overlays above the terrain tile

### R2: Agent Sprites

Agent sprites MUST render with faction-color tinting in the World container. Positions MUST interpolate smoothly between ticks using PixiJS Ticker.

#### Scenario: Faction color tint
- GIVEN a `fighter` agent with faction `red`
- WHEN the agent sprite renders
- THEN it displays the configured faction color

#### Scenario: Smooth movement
- GIVEN an agent at (10,10) that moves to (15,10) next tick
- WHEN intermediate frames render
- THEN sprite position interpolates toward (15,10) over tick duration

### R3: Particle Effects

Particle effects (harvest bursts, ambient dust, rain/snow) MUST render in the Effects container via PIXI.ParticleContainer for GPU batching.

#### Scenario: Harvest burst
- GIVEN an agent completes GATHER at a tile
- WHEN the harvest burst spawns
- THEN particles emit from the tile position and fade within 500ms

#### Scenario: Rain particles
- GIVEN simulation state includes rain weather
- THEN rain particles fall across the viewport in the Effects container

### R4: Camera Pan/Zoom

The camera SHOULD provide pan and zoom via pixi-viewport. Camera boundaries MUST clamp to the 50×50 grid extent.

#### Scenario: Pan clamps to grid edge
- GIVEN the camera is at grid origin (0,0)
- WHEN the user pans left/up
- THEN the camera position clamps to the grid boundary

#### Scenario: Zoom preserves appearance
- GIVEN grid at zoom 1.0
- WHEN the user zooms to 2.0
- THEN tiles render at 2× scale with no visual artifacts

### R5: Day/Night Filter

A PIXI.ColorMatrixFilter on the Effects container SHOULD tint the scene based on simulation daytime value (0=midnight, 1=noon).

#### Scenario: Night tint applied
- GIVEN simulation daytime = 0
- WHEN the color matrix updates
- THEN the scene renders with a dark blue-night tint

### R6: DOM Label Overlay

Agent name labels and speech bubbles MUST render as absolutely-positioned DOM elements, synced via container.toGlobal() each animation frame (RAF, not Ticker).

#### Scenario: Label follows agent
- GIVEN an agent at screen position (200,300)
- WHEN the agent moves to (250,300)
- THEN the label DOM position updates within one RAF frame

#### Scenario: Speech bubble
- GIVEN an agent with an active speech message
- THEN a DOM speech bubble renders above the agent sprite
