import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Track mutable state for Sprite mocks
let spriteAlpha = 1;
let spriteScaleX = 1;
let spriteScaleY = 1;

const mockSet = vi.fn((x: number, y: number) => {
	// no-op for position.set
});
const mockScaleSet = vi.fn((x: number, y: number) => {
	spriteScaleX = x;
	spriteScaleY = y;
});
const mockAnchorSet = vi.fn();
const mockAddChild = vi.fn();
const mockRemoveChild = vi.fn();
const mockDestroy = vi.fn();
const mockGenerateTexture = vi.fn().mockReturnValue({
	destroy: vi.fn()
});
let spriteTint = 0xffffff;

function resetSprites() {
	spriteAlpha = 1;
	spriteScaleX = 1;
	spriteScaleY = 1;
	spriteTint = 0xffffff;
}

vi.mock('pixi.js', () => ({
	Container: vi.fn().mockImplementation(() => ({
		addChild: mockAddChild,
		removeChild: mockRemoveChild,
		children: [] as any[]
	})),
	Graphics: vi.fn().mockImplementation(() => ({
		circle: vi.fn().mockReturnThis(),
		fill: vi.fn().mockReturnThis(),
		destroy: vi.fn()
	})),
	Sprite: vi.fn().mockImplementation(() => ({
		texture: {},
		position: { x: 0, y: 0, set: mockSet },
		width: 16,
		height: 16,
		anchor: { set: mockAnchorSet },
		scale: {
			get x() {
				return spriteScaleX;
			},
			set x(v: number) {
				spriteScaleX = v;
			},
			get y() {
				return spriteScaleY;
			},
			set y(v: number) {
				spriteScaleY = v;
			},
			set: mockScaleSet
		},
		get alpha() {
			return spriteAlpha;
		},
		set alpha(v: number) {
			spriteAlpha = v;
		},
		get tint() {
			return spriteTint;
		},
		set tint(v: number) {
			spriteTint = v;
		},
		destroy: mockDestroy
	})),
	ParticleContainer: vi.fn().mockImplementation(() => ({
		addChild: mockAddChild,
		removeChild: mockRemoveChild,
		children: [] as any[]
	}))
}));

import { EffectsLayer } from '../EffectsLayer';
import { Container } from 'pixi.js';

describe('EffectsLayer', () => {
	let effectsContainer: Container;
	let mockRenderer: any;
	let effects: EffectsLayer;

	beforeEach(() => {
		vi.clearAllMocks();
		resetSprites();
		effectsContainer = new Container();
		mockRenderer = {
			generateTexture: mockGenerateTexture
		};
		effects = new EffectsLayer(effectsContainer, mockRenderer);
	});

	afterEach(() => {
		try {
			effects.destroy();
		} catch {
			// Ignore destroy errors in cleanup
		}
	});

	it('should create particle textures on construction', () => {
		expect(mockGenerateTexture).toHaveBeenCalled();
	});

	it('should spawn particles when spawnHarvestBurst is called', () => {
		const burstCount = effects.getBurstParticleCount();
		expect(burstCount).toBe(0);

		effects.spawnHarvestBurst(100, 200, 'berries');
		const newCount = effects.getBurstParticleCount();
		expect(newCount).toBeGreaterThan(0);
	});

	it('should spawn the correct number of harvest particles (15)', () => {
		effects.spawnHarvestBurst(50, 50, 'trees');
		expect(effects.getBurstParticleCount()).toBe(15);
		expect(mockAddChild).toHaveBeenCalled();
	});

	it('should animate particles on update tick (fade and move)', () => {
		effects.spawnHarvestBurst(100, 100, 'iron_ore');

		// Tick multiple times
		for (let i = 0; i < 30; i++) {
			effects.update(1);
		}

		// After many ticks, alpha should be lower (fading out)
		expect(spriteAlpha).toBeLessThan(1);
	});

	it('should remove completed particles after their lifetime', () => {
		effects.spawnHarvestBurst(100, 100, 'stone');

		// Tick enough to exceed 500ms lifetime (delta=1 per tick)
		for (let i = 0; i < 60; i++) {
			effects.update(1);
		}

		expect(effects.getBurstParticleCount()).toBe(0);
	});

	it('should spawn particles of different color based on type', () => {
		effects.spawnHarvestBurst(100, 100, 'berries');
		const berryTint = spriteTint;

		effects.spawnHarvestBurst(200, 200, 'stone');

		// Different resource types should have different colors
		expect(spriteTint).not.toBe(berryTint);
	});

	it('should have ambient dust disabled', () => {
		// Ambient dust is disabled (AMBIENT_COUNT = 0) to reduce visual noise
		expect(effects['AMBIENT_COUNT']).toBe(0);
	});

	it('should clear all particles on destroy', () => {
		effects.spawnHarvestBurst(50, 50, 'trees');
		expect(effects.getBurstParticleCount()).toBeGreaterThan(0);

		effects.destroy();

		expect(effects.getBurstParticleCount()).toBe(0);
	});
});
