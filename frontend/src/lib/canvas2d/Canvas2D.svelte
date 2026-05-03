<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { Application, Container } from 'pixi.js';
	import { simulationStore } from '$lib/stores/simulationStore.svelte.js';
	import { uiStore } from '$lib/stores/uiStore.svelte.js';
	import { send } from '$lib/components/ws.js';
	import { canvas2dStore } from './canvas2dStore';
	import { createViewport } from './CameraControls';
	import { TileGrid } from './TileGrid';
	import { AgentSprites } from './AgentSprites';
	import { EffectsLayer } from './EffectsLayer';
	import { DayNightFilter } from './DayNightFilter';
	import { OverlayLayer } from './OverlayLayer';
	import { LabelSync } from './LabelSync';
	import type { Viewport } from 'pixi-viewport';

	let canvas: HTMLCanvasElement;
	let labelOverlay: HTMLDivElement;
	let app: Application;
	let viewport: Viewport;
	let worldContainer: Container;
	let effectsContainer: Container;
	let overlayContainer: Container;
	let tileGrid: TileGrid;
	let agentSprites: AgentSprites;
	let effectsLayer: EffectsLayer;
	let dayNightFilter: DayNightFilter;
	let overlayLayer: OverlayLayer;
	let labelSync: LabelSync;

	const GRID_SIZE = 80;
	const TILE_SIZE = 32;

	onMount(async () => {
		// Initialize PixiJS Application
		app = new Application();
		await app.init({
			canvas,
			width: canvas.parentElement?.clientWidth ?? 800,
			height: canvas.parentElement?.clientHeight ?? 600,
			background: '#1a1a2e',
			antialias: true,
			resolution: window.devicePixelRatio || 1,
			autoDensity: true
		});

		// Create viewport on stage (camera pans/zooms everything inside it)
		viewport = createViewport(app, {
			gridWidth: GRID_SIZE,
			gridHeight: GRID_SIZE,
			tileSize: TILE_SIZE
		});

		// Create container hierarchy inside the viewport so everything
		// moves together with the camera
		worldContainer = new Container();
		effectsContainer = new Container();
		overlayContainer = new Container();

		// Add containers inside viewport in correct z-order
		viewport.addChild(worldContainer);
		viewport.addChild(effectsContainer);
		viewport.addChild(overlayContainer);

		// Build tile grid inside worldContainer
		tileGrid = new TileGrid(worldContainer, GRID_SIZE, TILE_SIZE);
		tileGrid.build(app.renderer);

		// Create agent sprite manager inside worldContainer
		agentSprites = new AgentSprites(worldContainer, app.renderer);

		// Create effects layer (harvest bursts, ambient dust, weather)
		effectsLayer = new EffectsLayer(effectsContainer, app.renderer);

		// Create day/night filter on world + effects containers
		dayNightFilter = new DayNightFilter([worldContainer, effectsContainer]);

		// Create overlay layer (selection highlight)
		overlayLayer = new OverlayLayer(overlayContainer);

		// Create label sync with viewport for world→screen coordinate conversion
		labelSync = new LabelSync(viewport, labelOverlay);

		// Drive interpolation, sprite updates, and effects from PixiJS Ticker
		app.ticker.add(() => {
			canvas2dStore.tick(app.ticker.deltaTime);
			agentSprites.syncPositions(canvas2dStore.agentPositions);
			effectsLayer.update(app.ticker.deltaTime);

			// Selection ring: update position to follow the agent each frame
			const selectedId = overlayLayer?.getTargetAgentId();
			if (selectedId) {
				const pos = canvas2dStore.agentPositions[selectedId];
				if (pos) {
					overlayLayer.setPosition(pos.x, pos.y);
				}
			}
			overlayLayer.update(app.ticker.deltaTime);

			// Push current dialogue bubbles to label sync each tick
			if (labelSync) {
				labelSync.updateBubbles(canvas2dStore.dialogueBubbles);
			}
		});

		// Start label sync RAF loop
		labelSync.start();

		// Handle resize
		const resizeObserver = new ResizeObserver(() => {
			if (app && canvas.parentElement) {
				const width = canvas.parentElement.clientWidth;
				const height = canvas.parentElement.clientHeight;
				app.renderer.resize(width, height);
				viewport.resize(width, height);
			}
		});
		resizeObserver.observe(canvas.parentElement!);

		// Store for cleanup
		(canvas as HTMLCanvasElement & { __resizeObserver: ResizeObserver }).__resizeObserver =
			resizeObserver;
	});

	onDestroy(() => {
		if (labelSync) labelSync.destroy();
		if (overlayLayer) overlayLayer.destroy();
		if (dayNightFilter) dayNightFilter.destroy();
		if (effectsLayer) effectsLayer.destroy();
		if (tileGrid) tileGrid.destroy();
		if (agentSprites) agentSprites.destroy();
		if (app) {
			app.destroy(true);
		}
	});

	// Track previous agent actions for harvest burst detection
	let previousActions: Record<string, string | null> = {};

	/**
	 * Right-click handler for director mode move_to commands.
	 * When director mode is ON and an agent is selected, convert the click
	 * position to grid tile coordinates and send a move_to command.
	 * Otherwise, let the default browser context menu through.
	 */
	function handleContextMenu(event: MouseEvent) {
		const directorMode = $uiStore.directorMode;
		const selectedId = $uiStore.selectedAgentId;

		if (directorMode && selectedId && viewport && canvas) {
			event.preventDefault();

			// Convert page coordinates to canvas-relative pixel coordinates
			const rect = canvas.getBoundingClientRect();
			const canvasX = event.clientX - rect.left;
			const canvasY = event.clientY - rect.top;

			// Convert screen coordinates to world coordinates via pixi-viewport
			const worldPoint = viewport.toWorld(canvasX, canvasY);
			const tileX = Math.floor(worldPoint.x / TILE_SIZE);
			const tileY = Math.floor(worldPoint.y / TILE_SIZE);

			send({
				type: 'command',
				payload: {
					type: 'move_to',
					agent_id: selectedId,
					payload: { x: tileX, y: tileY }
				}
			});
		}
		// Otherwise: let default context menu through (e.g., for camera pan)
	}

	// Define minimal snapshot interface for what we actually access
	interface AgentEntry {
		name?: string;
		position?: [number, number];
		current_action?: string | null;
		role?: string;
		faction_id?: string;
		is_commanded?: boolean;
	}

	interface SnapshotData {
		agents?: Record<string, AgentEntry>;
		factions?: Record<string, { color: string }>;
		daytime?: number;
		time_state?: { is_night?: boolean; day_count?: number; time_of_day_label?: string };
		tiles?: Array<{
			x: number;
			y: number;
			resource_type: string | null;
			amount: number;
			subtype?: string | null;
		}>;
	}

	// Wire simulation store → canvas2dStore and all layers
	$effect(() => {
		const snapshot = $simulationStore as SnapshotData;
		if (snapshot && snapshot.agents) {
			canvas2dStore.updateTargets(snapshot, TILE_SIZE);

			// Sync tile resource overlays from snapshot tile data
			if (tileGrid && snapshot.tiles) {
				tileGrid.syncResources(app.renderer, snapshot.tiles);
			}

			// Update agent sprites from snapshot data (agents + factions)
			const factions = snapshot.factions ?? {};
			// Collect commanded agent IDs for badge indicators
			const commandedAgents = new Set<string>();
			for (const [id, agent] of Object.entries(snapshot.agents)) {
				if ((agent as AgentEntry).is_commanded) {
					commandedAgents.add(id);
				}
			}
			if (agentSprites) {
				agentSprites.update(
					snapshot.agents,
					factions as Record<string, { color: string }>,
					commandedAgents
				);
			}

			// Detect harvest actions and spawn burst particles
			if (effectsLayer) {
				for (const [id, agent] of Object.entries(snapshot.agents)) {
					const currentAction = agent.current_action ?? null;
					const prevAction = previousActions[id] ?? null;

					if (
						currentAction &&
						currentAction !== prevAction &&
						(currentAction.includes('harvest') ||
							currentAction.includes('gather') ||
							currentAction.includes('collect'))
					) {
						const pos = agent.position;
						if (pos) {
							// Convert grid coords to centered pixel coords, same as canvas2dStore
							const px = (pos[0] + 0.5) * TILE_SIZE;
							const py = (pos[1] + 0.5) * TILE_SIZE;
							// Extract resource type from action (e.g., "harvest_berries" → "berries")
							const parts = currentAction.split('_');
							const resourceType = parts.length > 1 ? parts.slice(1).join('_') : 'harvest';
							effectsLayer.spawnHarvestBurst(px, py, resourceType);
						}
					}

					previousActions[id] = currentAction;
				}
			}

			// Update label sync — scale grid positions to centered pixel coords
			if (labelSync) {
				const scaledAgents: Record<string, { name?: string; position?: [number, number] }> = {};
				for (const [id, agent] of Object.entries(snapshot.agents)) {
					scaledAgents[id] = agent;
					if (agent.position) {
						scaledAgents[id] = {
							...agent,
							position: [(agent.position[0] + 0.5) * TILE_SIZE, (agent.position[1] + 0.5) * TILE_SIZE]
						};
					}
				}
				labelSync.updateAgents(scaledAgents);
			}

			// Update day/night filter — use time_state.daytime or derive from is_night
			if (dayNightFilter) {
				const timeState = snapshot.time_state;
				if (timeState && typeof timeState.is_night === 'boolean') {
					dayNightFilter.update(timeState.is_night ? 0 : 0.5);
				} else if (typeof snapshot.daytime === 'number') {
					dayNightFilter.update(snapshot.daytime);
				}
			}
		}
	});

	// Wire uiStore.selectedAgentId → OverlayLayer (initial set only, Ticker follows)
	$effect(() => {
		const selectedId = $uiStore.selectedAgentId;
		if (overlayLayer && agentSprites) {
			if (selectedId) {
				const pos = canvas2dStore.agentPositions[selectedId];
				if (pos) {
					overlayLayer.setTarget(selectedId, pos.x, pos.y);
				} else {
					// Agent exists but position not yet known — set target anyway, Ticker will position it
					overlayLayer.setTarget(selectedId, 0, 0);
				}
			} else {
				overlayLayer.setTarget(null, 0, 0);
			}
		}
	});

	// Wire uiStore.directorMode → OverlayLayer ring color
	// Gold (0xffd700) when ON, green (0x00ff88) when OFF
	$effect(() => {
		const isDirectorMode = $uiStore.directorMode;
		if (overlayLayer) {
			overlayLayer.setRingColor(isDirectorMode ? 0xffd700 : 0x00ff88);
		}
	});
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="canvas-wrapper" oncontextmenu={handleContextMenu} role="application" style="position: relative; width: 100%; height: 100%;">
	<div class="canvas-container">
		<canvas bind:this={canvas} class="pixi-canvas"></canvas>
	</div>
	<div bind:this={labelOverlay} class="label-overlay"></div>
</div>

<style>
	.canvas-wrapper {
		position: relative;
		width: 100%;
		height: 100%;
	}

	.canvas-container {
		width: 100%;
		height: 100%;
		display: block;
		overflow: hidden;
	}

	.pixi-canvas {
		display: block;
		width: 100%;
		height: 100%;
	}

	.label-overlay {
		position: absolute;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
		pointer-events: none;
		overflow: hidden;
	}
</style>
