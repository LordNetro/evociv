# Delta for architecture

## MODIFIED Requirements

### R2: Canvas 2D Rendering Layer

The system MUST provide a 2D canvas rendering layer under `frontend/src/lib/canvas2d/` using PixiJS v8 with `pixi-viewport` for camera control. A `Canvas2D.svelte` component MUST mount the canvas and manage lifecycle. A `canvas2dStore.ts` MUST bridge simulation state to PixiJS objects.
(Previously: Five skeleton TypeScript files under `frontend/src/lib/canvas/` with skeleton classes for Engine, Grid, Entities, Animation, Camera.)

#### Scenario: Canvas2D mounts PixiJS
- GIVEN `Canvas2D.svelte` is rendered in a route
- WHEN the component mounts
- THEN a PixiJS `Application` initializes on a `<canvas>` element
- AND pixi-viewport is configured for pan/zoom

#### Scenario: Store bridges state
- GIVEN simulation produces new entity positions each tick
- WHEN `canvas2dStore` receives the tick data
- THEN PixiJS sprite positions update via Ticker interpolation
