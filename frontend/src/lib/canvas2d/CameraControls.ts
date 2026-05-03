import { Viewport } from 'pixi-viewport';
import type { Application } from 'pixi.js';

export interface CameraConfig {
	gridWidth: number;
	gridHeight: number;
	tileSize: number;
	minZoom?: number;
	maxZoom?: number;
}

/**
 * Creates and configures a pixi-viewport instance for pan/zoom camera control.
 * Drag pan, scroll wheel zoom, pinch zoom, deceleration, and grid-edge clamping.
 * The viewport is added directly to the stage (world content goes inside it).
 */
export function createViewport(app: Application, config: CameraConfig): Viewport {
	const worldWidth = config.gridWidth * config.tileSize;
	const worldHeight = config.gridHeight * config.tileSize;
	const minZoom = config.minZoom ?? 0.15;
	const maxZoom = config.maxZoom ?? 3.0;

	const viewport = new Viewport({
		screenWidth: app.renderer.width / app.renderer.resolution,
		screenHeight: app.renderer.height / app.renderer.resolution,
		worldWidth,
		worldHeight,
		events: app.renderer.events,
		stopPropagation: true,
		passiveWheel: false
	});

	// Add plugins
	viewport
		.drag({
			mouseButtons: 'left',
			wheel: false
		})
		.wheel({
			percent: 0.1,
			smooth: 6,
			axis: 'all',
			trackpadPinch: true,
			wheelZoom: true
		})
		.pinch({
			axis: 'all'
		})
		.decelerate({
			friction: 0.85,
			minSpeed: 0.5
		})
		.clampZoom({
			minScale: minZoom,
			maxScale: maxZoom
		});

	// Add to stage
	app.stage.addChild(viewport);

	return viewport;
}
