import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock PIXI primitives
const mockAddChild = vi.fn();
const mockRemoveChild = vi.fn();
const mockDestroy = vi.fn();
const mockGenerateTexture = vi.fn().mockReturnValue({
	destroy: vi.fn()
});

vi.mock('pixi.js', () => ({
	Container: vi.fn().mockImplementation(() => ({
		addChild: mockAddChild,
		removeChild: mockRemoveChild,
		children: [] as any[]
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
		destroy: mockDestroy
	})),
	Texture: {
		from: vi.fn().mockReturnValue({})
	}
}));

import { TileGrid } from '../TileGrid';
import { Container } from 'pixi.js';

describe('TileGrid', () => {
	const GRID_SIZE = 50;
	const TILE_SIZE = 16;

	let worldContainer: Container;
	let mockRenderer: any;

	beforeEach(() => {
		vi.clearAllMocks();
		worldContainer = new Container();
		mockRenderer = {
			generateTexture: mockGenerateTexture
		};
	});

	it('should create a procedural atlas via Graphics + generateTexture', () => {
		const tileGrid = new TileGrid(worldContainer, GRID_SIZE, TILE_SIZE);
		tileGrid.build(mockRenderer);

		expect(mockGenerateTexture).toHaveBeenCalled();
		expect(tileGrid.atlas).toBeDefined();
	});

	it('should position 2500 tile sprites correctly in the grid', () => {
		const tileGrid = new TileGrid(worldContainer, GRID_SIZE, TILE_SIZE);
		tileGrid.build(mockRenderer);

		// Should have added 2500 terrain sprites
		const addChildCalls = mockAddChild.mock.calls.length;
		expect(addChildCalls).toBe(GRID_SIZE * GRID_SIZE);
	});

	it('should have the correct number of tile sprites', () => {
		const tileGrid = new TileGrid(worldContainer, GRID_SIZE, TILE_SIZE);
		tileGrid.build(mockRenderer);

		expect(tileGrid.tileSprites.length).toBe(GRID_SIZE * GRID_SIZE);
	});

	it('should add resource overlay sprites on top of tiles', () => {
		const tileGrid = new TileGrid(worldContainer, GRID_SIZE, TILE_SIZE);
		tileGrid.build(mockRenderer);

		// Add a resource overlay
		tileGrid.addResourceOverlay(mockRenderer, 10, 15, 'iron_ore');

		expect(tileGrid.resourceSprites.length).toBe(1);
		expect(tileGrid.resourceSprites[0].tileX).toBe(10);
		expect(tileGrid.resourceSprites[0].tileY).toBe(15);
		expect(tileGrid.resourceSprites[0].resourceType).toBe('iron_ore');
	});

	it('should remove resource overlay by tile position', () => {
		const tileGrid = new TileGrid(worldContainer, GRID_SIZE, TILE_SIZE);
		tileGrid.build(mockRenderer);
		tileGrid.addResourceOverlay(mockRenderer, 5, 5, 'trees');

		tileGrid.removeResourceOverlay(5, 5);

		expect(tileGrid.resourceSprites.length).toBe(0);
	});

	it('should destroy all sprites on cleanup', () => {
		const tileGrid = new TileGrid(worldContainer, GRID_SIZE, TILE_SIZE);
		tileGrid.build(mockRenderer);
		tileGrid.addResourceOverlay(mockRenderer, 3, 7, 'water');

		tileGrid.destroy();

		expect(tileGrid.tileSprites.length).toBe(0);
		expect(tileGrid.resourceSprites.length).toBe(0);
		expect(tileGrid.atlas).toBeNull();
	});
});
