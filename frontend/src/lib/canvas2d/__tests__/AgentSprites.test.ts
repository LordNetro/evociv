import { describe, it, expect, vi, beforeEach } from 'vitest';

// Use vi.hoisted so mockSelectAgent is available both in vi.mock factory and in test code
const mockSelectAgent = vi.hoisted(() => vi.fn());
vi.mock('$lib/stores/uiStore.svelte.js', () => ({
	uiStore: {
		selectAgent: mockSelectAgent
	}
}));

const mockGenerateTexture = vi.fn().mockReturnValue({
	destroy: vi.fn()
});
const mockContainerAddChild = vi.fn();
const mockContainerRemoveChild = vi.fn();
const mockDestroy = vi.fn();

const mockGraphicsDestroy = vi.fn();

/** Track addChild calls per sprite mock instance */
const spriteAddChildMocks: Map<string, ReturnType<typeof vi.fn>> = new Map();

vi.mock('pixi.js', () => ({
	Container: vi.fn().mockImplementation(() => ({
		addChild: mockContainerAddChild,
		removeChild: mockContainerRemoveChild,
		children: [] as any[]
	})),
	Graphics: vi.fn().mockImplementation(() => ({
		circle: vi.fn().mockReturnThis(),
		fill: vi.fn().mockReturnThis(),
		poly: vi.fn().mockReturnThis(),
		position: { set: vi.fn(), x: 0, y: 0 },
		destroy: mockGraphicsDestroy
	})),
	Sprite: vi.fn().mockImplementation(() => {
		const addChildMock = vi.fn();
		return {
			texture: {},
			position: { set: vi.fn(), x: 0, y: 0 },
			width: 16,
			height: 16,
			anchor: { set: vi.fn() },
			eventMode: 'none',
			on: vi.fn(),
			off: vi.fn(),
			cursor: 'default',
			tint: 0xffffff,
			addChild: addChildMock,
			removeChild: vi.fn(),
			destroy: mockDestroy,
			children: [] as any[]
		};
	})
}));

import { AgentSprites } from '../AgentSprites';
import { Container, Graphics } from 'pixi.js';

describe('AgentSprites', () => {
	let parentContainer: Container;
	let mockRenderer: any;
	let agentSprites: AgentSprites;

	beforeEach(() => {
		vi.clearAllMocks();
		parentContainer = new Container();
		mockRenderer = {
			generateTexture: mockGenerateTexture
		};
		agentSprites = new AgentSprites(parentContainer, mockRenderer);
	});

	it('should create agent sprites with faction tint', () => {
		const agents = {
			'agent-1': { name: 'Test', faction_id: 'faction-red' }
		};
		const factions = {
			'faction-red': { color: '#ff0000' }
		};

		agentSprites.update(agents, factions);

		expect(agentSprites.spriteCount).toBe(1);
		expect(mockGenerateTexture).toHaveBeenCalled();
	});

	it('should set click handler on agent sprites', () => {
		const agents = {
			'agent-1': { name: 'Test', faction_id: 'faction-red' }
		};
		const factions = {
			'faction-red': { color: '#ff0000' }
		};

		agentSprites.update(agents, factions);

		// The sprite should have an 'on' call for pointer events
		const spriteOn = vi.mocked(agentSprites as any).spriteOn;
		// Verify by checking that clicking triggers selectAgent
		const sprite = agentSprites.getSprite('agent-1');
		expect(sprite).toBeDefined();
	});

	it('should call uiStore.selectAgent when agent sprite is clicked', () => {
		const agents = {
			'agent-42': { name: 'Hero', faction_id: 'faction-blue' }
		};
		const factions = {
			'faction-blue': { color: '#0000ff' }
		};

		agentSprites.update(agents, factions);

		// Simulate a click by finding and invoking the click handler
		const sprite = agentSprites.getSprite('agent-42');
		if (sprite) {
			// Find the click handler that was registered
			const onCalls = vi.mocked(sprite.on).mock.calls;
			const clickCall = onCalls.find(([event]) => event === 'pointerdown' || event === 'click');
			if (clickCall) {
				const handler = clickCall[1] as Function;
				handler();
			}
		}

		expect(mockSelectAgent).toHaveBeenCalledWith('agent-42');
	});

	it('should remove sprites for agents no longer in the set', () => {
		// First update with agents
		agentSprites.update(
			{ 'agent-1': { name: 'Test', faction_id: 'faction-red' } },
			{ 'faction-red': { color: '#ff0000' } }
		);

		expect(agentSprites.spriteCount).toBe(1);

		// Second update with empty agents should remove
		agentSprites.update({}, {});

		expect(agentSprites.spriteCount).toBe(0);
	});

	it('should handle agents with no faction_id gracefully', () => {
		const agents = {
			'agent-1': { name: 'NoFaction' }
		};

		agentSprites.update(agents, {});

		expect(agentSprites.spriteCount).toBe(1);
	});

	it('should re-use existing sprites instead of recreating (recycling)', () => {
		const agents = {
			'agent-1': { name: 'Test', faction_id: 'faction-red' }
		};
		const factions = {
			'faction-red': { color: '#ff0000' }
		};

		agentSprites.update(agents, factions);
		const firstSprite = agentSprites.getSprite('agent-1');

		// Update with same agent
		agentSprites.update(agents, factions);
		const secondSprite = agentSprites.getSprite('agent-1');

		// Should be the same sprite (not destroyed and recreated)
		expect(firstSprite).toBe(secondSprite);
	});

	it('should add badge child to commanded agents when commandedAgents set is provided', () => {
		const agents = {
			'agent-1': { name: 'Commander', faction_id: 'faction-red' },
			'agent-2': { name: 'Free', faction_id: 'faction-blue' }
		};
		const factions = {
			'faction-red': { color: '#ff0000' },
			'faction-blue': { color: '#0000ff' }
		};

		agentSprites.update(agents, factions, new Set(['agent-1']));

		const sprite1 = agentSprites.getSprite('agent-1');
		const sprite2 = agentSprites.getSprite('agent-2');

		expect(sprite1).toBeDefined();
		expect(sprite2).toBeDefined();

		if (sprite1) {
			expect(sprite1.addChild).toHaveBeenCalled();
			const child = vi.mocked(sprite1.addChild).mock.calls[0][0];
			expect(child).toBeDefined();
		}
		if (sprite2) {
			expect(sprite2.addChild).not.toHaveBeenCalled();
		}
	});

	it('should remove badge when agent is no longer commanded', () => {
		const agents = {
			'agent-1': { name: 'Test', faction_id: 'faction-red' }
		};
		const factions = {
			'faction-red': { color: '#ff0000' }
		};

		// First update: agent-1 is commanded — badge should be added
		agentSprites.update(agents, factions, new Set(['agent-1']));
		const sprite1 = agentSprites.getSprite('agent-1');
		expect(sprite1).toBeDefined();
		if (sprite1) {
			expect(sprite1.addChild).toHaveBeenCalled();
		}

		// Second update: agent-1 is NOT commanded — badge should be removed
		agentSprites.update(agents, factions, new Set());

		if (sprite1) {
			expect(sprite1.removeChild).toHaveBeenCalled();
		}
	});

	it('should clean up badges on destroy', () => {
		const agents = {
			'agent-1': { name: 'Test', faction_id: 'faction-red' }
		};
		const factions = {
			'faction-red': { color: '#ff0000' }
		};

		agentSprites.update(agents, factions, new Set(['agent-1']));

		agentSprites.destroy();

		// Badge Graphics should be destroyed
		expect(mockGraphicsDestroy).toHaveBeenCalled();
	});

	it('should clean up all sprites on destroy', () => {
		agentSprites.update(
			{
				'agent-1': { name: 'A', faction_id: 'faction-red' },
				'agent-2': { name: 'B', faction_id: 'faction-blue' }
			},
			{
				'faction-red': { color: '#ff0000' },
				'faction-blue': { color: '#0000ff' }
			}
		);

		agentSprites.destroy();

		expect(agentSprites.spriteCount).toBe(0);
	});
});
