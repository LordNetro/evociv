import { describe, it, expect, vi, beforeEach } from 'vitest';

// Shared mutable state for Graphics mock — tests can read values set by implementation
let graphicsAlpha = 1;
let graphicsPosX = 0;
let graphicsPosY = 0;
let graphicsScaleX = 1;
let graphicsScaleY = 1;
let lastStrokeColor: number | undefined;

const mockSet = vi.fn((x: number, y: number) => {
	graphicsPosX = x;
	graphicsPosY = y;
});
const mockScaleSet = vi.fn((x: number, y: number) => {
	graphicsScaleX = x;
	graphicsScaleY = y;
});
const mockClear = vi.fn();
const mockCircle = vi.fn().mockReturnThis();
const mockFill = vi.fn().mockReturnThis();
const mockStroke = vi.fn().mockImplementation((opts: { color?: number }) => {
	lastStrokeColor = opts.color;
});
const mockDestroyGraphics = vi.fn();
const mockAddChild = vi.fn();
const mockRemoveChild = vi.fn();

function resetGraphicsState() {
	graphicsAlpha = 1;
	graphicsPosX = 0;
	graphicsPosY = 0;
	graphicsScaleX = 1;
	graphicsScaleY = 1;
	lastStrokeColor = undefined;
}

vi.mock('pixi.js', () => ({
	Container: vi.fn().mockImplementation(() => ({
		addChild: mockAddChild,
		removeChild: mockRemoveChild,
		children: [] as any[]
	})),
	Graphics: vi.fn().mockImplementation(() => ({
		clear: mockClear,
		circle: mockCircle,
		fill: mockFill,
		stroke: mockStroke,
		position: {
			get x() {
				return graphicsPosX;
			},
			set x(v: number) {
				graphicsPosX = v;
			},
			get y() {
				return graphicsPosY;
			},
			set y(v: number) {
				graphicsPosY = v;
			},
			set: mockSet
		},
		scale: {
			get x() {
				return graphicsScaleX;
			},
			set x(v: number) {
				graphicsScaleX = v;
			},
			get y() {
				return graphicsScaleY;
			},
			set y(v: number) {
				graphicsScaleY = v;
			},
			set: mockScaleSet
		},
		get alpha() {
			return graphicsAlpha;
		},
		set alpha(v: number) {
			graphicsAlpha = v;
		},
		destroy: mockDestroyGraphics
	}))
}));

import { OverlayLayer } from '../OverlayLayer';
import { Container, Graphics } from 'pixi.js';

describe('OverlayLayer', () => {
	let overlayContainer: Container;
	let overlay: OverlayLayer;

	beforeEach(() => {
		vi.clearAllMocks();
		resetGraphicsState();
		overlayContainer = new Container();
		overlay = new OverlayLayer(overlayContainer);
	});

	it('should create a Graphics object in the container', () => {
		expect(mockAddChild).toHaveBeenCalled();
		expect(Graphics).toHaveBeenCalled();
	});

	it('should initially be invisible (alpha 0)', () => {
		expect(graphicsAlpha).toBe(0);
	});

	it('should draw a ring at the target position when setTarget is called', () => {
		overlay.setTarget('agent-1', 100, 200);

		expect(overlay.getTargetAgentId()).toBe('agent-1');
		expect(graphicsPosX).toBe(100);
		expect(graphicsPosY).toBe(200);
		expect(graphicsAlpha).toBe(0.7);
	});

	it('should clear previous graphics and redraw when target updates', () => {
		overlay.setTarget('agent-1', 100, 200);
		expect(mockClear).toHaveBeenCalled();

		overlay.setTarget('agent-1', 300, 400);

		expect(mockClear).toHaveBeenCalledTimes(2);
		expect(graphicsPosX).toBe(300);
		expect(graphicsPosY).toBe(400);
	});

	it('should hide the ring when target is set to null', () => {
		overlay.setTarget('agent-1', 100, 200);
		expect(graphicsAlpha).toBe(0.7);

		overlay.setTarget(null, 0, 0);
		expect(overlay.getTargetAgentId()).toBeNull();
		expect(graphicsAlpha).toBe(0);
	});

	it('should update scale for pulsing animation on tick', () => {
		overlay.setTarget('agent-1', 100, 200);

		overlay.update(1);
		// Scale should have changed due to pulsing animation
		expect(graphicsScaleX).not.toBe(1);
		expect(graphicsScaleY).not.toBe(1);
	});

	it('should not animate when no target is set', () => {
		overlay.setTarget(null, 0, 0);
		const scaleBefore = graphicsScaleX;

		overlay.update(1);

		expect(graphicsScaleX).toBe(scaleBefore);
	});

	it('should use default ring color 0x00ff88 (green)', () => {
		overlay.setTarget('agent-1', 100, 200);
		expect(lastStrokeColor).toBe(0x00ff88);
	});

	it('should change ring color when setRingColor is called', () => {
		overlay.setRingColor(0xffd700);
		overlay.setTarget('agent-1', 100, 200);
		expect(lastStrokeColor).toBe(0xffd700);
	});

	it('should preserve ring color across multiple setTarget calls', () => {
		overlay.setRingColor(0xffd700);
		overlay.setTarget('agent-1', 100, 200);
		expect(lastStrokeColor).toBe(0xffd700);

		overlay.setTarget('agent-2', 300, 400);
		expect(lastStrokeColor).toBe(0xffd700);
	});

	it('should revert to green when setRingColor is set back to 0x00ff88', () => {
		overlay.setRingColor(0xffd700);
		overlay.setTarget('agent-1', 100, 200);
		expect(lastStrokeColor).toBe(0xffd700);

		overlay.setRingColor(0x00ff88);
		overlay.setTarget('agent-1', 200, 300);
		expect(lastStrokeColor).toBe(0x00ff88);
	});

	it('should remove from container and destroy on cleanup', () => {
		overlay.destroy();

		expect(mockRemoveChild).toHaveBeenCalled();
		expect(mockDestroyGraphics).toHaveBeenCalled();
	});
});
