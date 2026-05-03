import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { canvas2dStore, type AgentPosition } from '../canvas2dStore';

describe('Canvas2DStore', () => {
	beforeEach(() => {
		// Reset store state
		canvas2dStore.agentPositions = {};
		canvas2dStore.targetPositions = {};
		canvas2dStore.lerpFactor = 0;
		canvas2dStore.dialogueBubbles = {};
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	describe('updateTargets()', () => {
		it('should store target positions and reset lerpFactor', () => {
			const snapshot = {
				agents: {
					'agent-1': { position: [10, 20] as [number, number] },
					'agent-2': { position: [30, 40] as [number, number] }
				}
			};

			canvas2dStore.updateTargets(snapshot);

			expect(canvas2dStore.targetPositions['agent-1']).toEqual({ x: 10.5, y: 20.5 });
			expect(canvas2dStore.targetPositions['agent-2']).toEqual({ x: 30.5, y: 40.5 });
			expect(canvas2dStore.lerpFactor).toBe(0);
		});

		it('should handle empty agents gracefully', () => {
			canvas2dStore.updateTargets({ agents: {} });
			expect(canvas2dStore.targetPositions).toEqual({});
		});

		it('should handle null/undefined snapshot', () => {
			canvas2dStore.updateTargets({});
			expect(canvas2dStore.targetPositions).toEqual({});
		});

		it('should store dialogue bubbles with correct type and expiry', () => {
			const before = Date.now();
			const snapshot = {
				agents: {
					'agent-1': {
						position: [0, 0] as [number, number],
						current_dialogue: 'Hello!',
						dialogue_type: 'speech'
					},
					'agent-2': {
						position: [1, 1] as [number, number],
						current_dialogue: 'Hmm...',
						dialogue_type: 'thought'
					}
				}
			};

			canvas2dStore.updateTargets(snapshot);

			expect(canvas2dStore.dialogueBubbles['agent-1']?.text).toBe('Hello!');
			expect(canvas2dStore.dialogueBubbles['agent-1']?.type).toBe('speech');
			expect(canvas2dStore.dialogueBubbles['agent-1']?.visibleUntil).toBeGreaterThanOrEqual(
				before + 3000
			);
			expect(canvas2dStore.dialogueBubbles['agent-2']?.text).toBe('Hmm...');
			expect(canvas2dStore.dialogueBubbles['agent-2']?.type).toBe('thought');
			expect(canvas2dStore.dialogueBubbles['agent-2']?.visibleUntil).toBeGreaterThanOrEqual(
				before + 5000
			);
		});

		it('should set dialogue bubble to null when no current_dialogue', () => {
			const snapshot = {
				agents: {
					'agent-1': {
						position: [0, 0] as [number, number]
					}
				}
			};

			canvas2dStore.updateTargets(snapshot);
			expect(canvas2dStore.dialogueBubbles['agent-1']).toBeNull();
		});
	});

	describe('tick()', () => {
		it('should lerp agent positions toward targets', () => {
			canvas2dStore.agentPositions = { 'agent-1': { x: 0, y: 0 } };
			canvas2dStore.targetPositions = { 'agent-1': { x: 100, y: 100 } };
			canvas2dStore.tick(0.5);

			const pos = canvas2dStore.agentPositions['agent-1'];
			// With delta=0.5, speed = min(0.5*10, 1) = 1, so 100% lerp
			expect(pos.x).toBe(100);
			expect(pos.y).toBe(100);
		});

		it('should partially lerp with small delta values', () => {
			canvas2dStore.agentPositions = { 'agent-1': { x: 0, y: 0 } };
			canvas2dStore.targetPositions = { 'agent-1': { x: 100, y: 50 } };
			canvas2dStore.tick(0.03);

			const pos = canvas2dStore.agentPositions['agent-1'];
			// speed = min(0.03*10, 1) = 0.3
			// x = 0 + (100 - 0) * 0.3 = 30
			// y = 0 + (50 - 0) * 0.3 = 15
			expect(pos.x).toBeCloseTo(30);
			expect(pos.y).toBeCloseTo(15);
		});

		it('should snap new agents to target position', () => {
			canvas2dStore.agentPositions = {};
			canvas2dStore.targetPositions = { 'agent-1': { x: 50, y: 75 } };
			canvas2dStore.tick(0.1);

			expect(canvas2dStore.agentPositions['agent-1']).toEqual({ x: 50, y: 75 });
		});

		it('should remove agents that have no target', () => {
			canvas2dStore.agentPositions = { 'old-agent': { x: 10, y: 10 } };
			canvas2dStore.targetPositions = {};
			canvas2dStore.tick(0.1);

			expect(canvas2dStore.agentPositions['old-agent']).toBeUndefined();
		});

		it('should expire old dialogue bubbles', () => {
			canvas2dStore.dialogueBubbles = {
				'agent-1': {
					text: 'old message',
					type: 'speech',
					visibleUntil: Date.now() - 1000 // expired
				},
				'agent-2': {
					text: 'current message',
					type: 'speech',
					visibleUntil: Date.now() + 10000 // still valid
				}
			};

			canvas2dStore.tick(0.1);

			expect(canvas2dStore.dialogueBubbles['agent-1']).toBeNull();
			expect(canvas2dStore.dialogueBubbles['agent-2']?.text).toBe('current message');
		});

		it('should converge to target positions over multiple ticks (lerpFactor accumulation)', () => {
			canvas2dStore.agentPositions = { 'agent-1': { x: 0, y: 0 } };
			canvas2dStore.targetPositions = { 'agent-1': { x: 200, y: 0 } };

			// Tick multiple times with medium delta
			canvas2dStore.tick(0.05); // speed = 0.5, x = 0 + 200*0.5 = 100
			expect(canvas2dStore.agentPositions['agent-1'].x).toBeCloseTo(100);

			canvas2dStore.tick(0.05); // speed = 0.5, x = 100 + 100*0.5 = 150
			expect(canvas2dStore.agentPositions['agent-1'].x).toBeCloseTo(150);

			canvas2dStore.tick(0.05); // speed = 0.5, x = 150 + 50*0.5 = 175
			expect(canvas2dStore.agentPositions['agent-1'].x).toBeCloseTo(175);
		});
	});
});
