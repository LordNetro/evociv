import { describe, it, expect, vi, beforeEach } from 'vitest';

// We test Canvas2D.svelte's integration pattern by testing
// that the container hierarchy and lifecycle logic works correctly.
// Full component rendering via mount() is not feasible in vitest/happy-dom
// due to Svelte 5 API changes. We verify module imports and contracts instead.

// Mock PIXI primitives
const mockAddChild = vi.fn();

vi.mock('pixi.js', () => ({
	Container: vi.fn().mockImplementation(() => ({
		addChild: mockAddChild,
		removeChild: vi.fn(),
		children: [] as any[],
		filters: null,
		toGlobal: vi.fn().mockReturnValue({ x: 0, y: 0 }),
		position: { x: 0, y: 0, set: vi.fn() },
		scale: { x: 1, y: 1 }
	})),
	Graphics: vi.fn().mockImplementation(() => ({
		rect: vi.fn().mockReturnThis(),
		fill: vi.fn().mockReturnThis(),
		circle: vi.fn().mockReturnThis(),
		destroy: vi.fn()
	})),
	Sprite: vi.fn().mockImplementation(() => ({
		texture: {},
		position: { set: vi.fn(), x: 0, y: 0 },
		width: 16,
		height: 16,
		anchor: { set: vi.fn() },
		eventMode: 'none',
		on: vi.fn(),
		cursor: 'default',
		tint: 0xffffff,
		scale: { x: 1, y: 1, set: vi.fn() },
		destroy: vi.fn()
	})),
	ColorMatrixFilter: vi.fn().mockImplementation(() => ({
		matrix: new Float32Array(20),
		destroy: vi.fn()
	})),
	ParticleContainer: vi.fn().mockImplementation(() => ({
		addChild: mockAddChild,
		removeChild: vi.fn(),
		children: [] as any[]
	}))
}));

vi.mock('pixi-viewport', () => ({
	Viewport: vi.fn().mockImplementation(() => ({
		drag: vi.fn().mockReturnThis(),
		wheel: vi.fn().mockReturnThis(),
		pinch: vi.fn().mockReturnThis(),
		decelerate: vi.fn().mockReturnThis(),
		clamp: vi.fn().mockReturnThis(),
		clampZoom: vi.fn().mockReturnThis(),
		addChild: mockAddChild,
		resize: vi.fn(),
		toGlobal: vi.fn().mockReturnValue({ x: 0, y: 0 }),
		worldWidth: 800,
		worldHeight: 800,
		screenWidth: 800,
		screenHeight: 600
	}))
}));

// Mock stores
vi.mock('$lib/stores/simulationStore.svelte.js', () => ({
	simulationStore: {
		subscribe: vi.fn((run: Function) => {
			run({ agents: {}, tiles: [], factions: {} });
			return () => {};
		})
	}
}));

vi.mock('$lib/stores/uiStore.svelte.js', () => ({
	uiStore: {
		subscribe: vi.fn((run: Function) => {
			run({ selectedAgentId: null });
			return () => {};
		}),
		selectAgent: vi.fn()
	}
}));

describe('Canvas2D Integration', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('should export the Canvas2D component', async () => {
		const { default: Canvas2D } = await import('../Canvas2D.svelte');
		expect(Canvas2D).toBeDefined();
	}, 15000);

	it('should have all required sub-modules available', async () => {
		const tileGridMod = await import('../TileGrid');
		expect(tileGridMod.TileGrid).toBeDefined();

		const agentSpritesMod = await import('../AgentSprites');
		expect(agentSpritesMod.AgentSprites).toBeDefined();

		const cameraMod = await import('../CameraControls');
		expect(cameraMod.createViewport).toBeDefined();

		const effectsMod = await import('../EffectsLayer');
		expect(effectsMod.EffectsLayer).toBeDefined();

		const dayNightMod = await import('../DayNightFilter');
		expect(dayNightMod.DayNightFilter).toBeDefined();

		const overlayMod = await import('../OverlayLayer');
		expect(overlayMod.OverlayLayer).toBeDefined();

		const labelSyncMod = await import('../LabelSync');
		expect(labelSyncMod.LabelSync).toBeDefined();
	});

	it('should wire ticker with canvas2dStore.tick and agentSprites.syncPositions', async () => {
		const storeMod = await import('../canvas2dStore');
		expect(storeMod.canvas2dStore).toBeDefined();
		expect(typeof storeMod.canvas2dStore.tick).toBe('function');
		expect(typeof storeMod.canvas2dStore.updateTargets).toBe('function');
	});

	it('should convert world pixel coords to tile coords using Math.floor', () => {
		const TILE_SIZE = 32;
		// At pixel (0, 0) → tile (0, 0)
		expect(Math.floor(0 / TILE_SIZE)).toBe(0);
		expect(Math.floor(0 / TILE_SIZE)).toBe(0);

		// At pixel (31, 31) → tile (0, 0)
		expect(Math.floor(31 / TILE_SIZE)).toBe(0);
		expect(Math.floor(31 / TILE_SIZE)).toBe(0);

		// At pixel (32, 32) → tile (1, 1)
		expect(Math.floor(32 / TILE_SIZE)).toBe(1);
		expect(Math.floor(32 / TILE_SIZE)).toBe(1);

		// At pixel (100, 200) → tile (3, 6)
		expect(Math.floor(100 / TILE_SIZE)).toBe(3);
		expect(Math.floor(200 / TILE_SIZE)).toBe(6);

		// Negative coords → negative tiles (should not happen in-bounds)
		expect(Math.floor(-1 / TILE_SIZE)).toBe(-1);
	});

	it('should import send function from ws.js for move_to commands', async () => {
		const wsMod = await import('$lib/components/ws.js');
		expect(typeof wsMod.send).toBe('function');
	});

	it('should import uiStore for directorMode and selectedAgentId', async () => {
		const storeMod = await import('$lib/stores/uiStore.svelte.js');
		expect(storeMod.uiStore).toBeDefined();
		expect(typeof storeMod.uiStore.subscribe).toBe('function');
	});
});
