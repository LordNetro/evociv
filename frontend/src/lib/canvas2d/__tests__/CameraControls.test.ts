import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock pixi-viewport before importing CameraControls
const mockDrag = vi.fn().mockReturnThis();
const mockWheel = vi.fn().mockReturnThis();
const mockPinch = vi.fn().mockReturnThis();
const mockDecelerate = vi.fn().mockReturnThis();
const mockClamp = vi.fn().mockReturnThis();
const mockClampZoom = vi.fn().mockReturnThis();
const mockStageAddChild = vi.fn();

vi.mock('pixi-viewport', () => {
	return {
		Viewport: vi.fn().mockImplementation(() => ({
			drag: mockDrag,
			wheel: mockWheel,
			pinch: mockPinch,
			decelerate: mockDecelerate,
			clamp: mockClamp,
			clampZoom: mockClampZoom,
			worldWidth: 800,
			worldHeight: 800,
			screenWidth: 800,
			screenHeight: 600,
			addChild: vi.fn()
		}))
	};
});

import { createViewport } from '../CameraControls';
import { Viewport } from 'pixi-viewport';

describe('CameraControls', () => {
	const mockApp = {
		renderer: {
			width: 800,
			height: 600,
			resolution: 1,
			events: {}
		},
		stage: {
			addChild: mockStageAddChild
		}
	} as any;

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('should create a viewport with correct dimensions', () => {
		const viewport = createViewport(mockApp, {
			gridWidth: 50,
			gridHeight: 50,
			tileSize: 16
		});

		expect(Viewport).toHaveBeenCalledWith(
			expect.objectContaining({
				screenWidth: 800,
				screenHeight: 600,
				worldWidth: 800,
				worldHeight: 800
			})
		);
		expect(viewport.worldWidth).toBe(800);
		expect(viewport.worldHeight).toBe(800);
	});

	it('should add the viewport to the stage', () => {
		const viewport = createViewport(mockApp, {
			gridWidth: 50,
			gridHeight: 50,
			tileSize: 16
		});

		expect(mockStageAddChild).toHaveBeenCalledWith(viewport);
	});

	it('should configure all viewport plugins', () => {
		createViewport(mockApp, {
			gridWidth: 50,
			gridHeight: 50,
			tileSize: 16
		});

		expect(mockDrag).toHaveBeenCalledWith(
			expect.objectContaining({
				mouseButtons: 'left'
			})
		);
		expect(mockWheel).toHaveBeenCalled();
		expect(mockPinch).toHaveBeenCalled();
		expect(mockDecelerate).toHaveBeenCalled();
		expect(mockClampZoom).toHaveBeenCalled();

		// Clamp is intentionally NOT used — user can pan beyond map edges
		expect(mockClamp).not.toHaveBeenCalled();
	});
});
