import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock PIXI primitives
vi.mock('pixi.js', () => ({
	Container: vi.fn().mockImplementation(() => ({
		toGlobal: vi.fn().mockReturnValue({ x: 100, y: 200 })
	}))
}));

import { LabelSync } from '../LabelSync';
import { Container } from 'pixi.js';

describe('LabelSync', () => {
	let worldContainer: Container;
	let labelContainer: HTMLElement;
	let labelSync: LabelSync;

	beforeEach(() => {
		worldContainer = new Container();
		labelContainer = document.createElement('div');
		labelContainer.id = 'label-overlay';
		labelContainer.style.position = 'absolute';
		labelContainer.style.top = '0';
		labelContainer.style.left = '0';
		labelContainer.style.pointerEvents = 'none';
		document.body.appendChild(labelContainer);

		labelSync = new LabelSync(worldContainer, labelContainer);
	});

	afterEach(() => {
		labelSync.destroy();
		document.body.removeChild(labelContainer);
	});

	it('should create DOM elements for agents', () => {
		const agents = {
			'agent-1': { name: 'Alice', position: [10, 20] as [number, number] },
			'agent-2': { name: 'Bob', position: [30, 40] as [number, number] }
		};

		labelSync.updateAgents(agents);

		const labels = labelContainer.querySelectorAll('[data-agent-id]');
		expect(labels.length).toBe(2);

		const label1 = labelContainer.querySelector('[data-agent-id="agent-1"]');
		expect(label1).toBeDefined();
		expect(label1!.textContent).toBe('Alice');
	});

	it('should remove DOM elements for agents that no longer exist', () => {
		labelSync.updateAgents({
			'agent-1': { name: 'Alice', position: [10, 20] as [number, number] }
		});
		expect(labelContainer.children.length).toBe(1);

		labelSync.updateAgents({});
		expect(labelContainer.children.length).toBe(0);
	});

	it('should position DOM elements using CSS transform on sync', () => {
		labelSync.updateAgents({
			'agent-1': { name: 'Alice', position: [10, 20] as [number, number] }
		});

		labelSync.sync();

		const label = labelContainer.querySelector('[data-agent-id="agent-1"]') as HTMLElement;
		expect(label).toBeDefined();
		expect(label.style.transform).toContain('translate');
	});

	it('should call toGlobal on the world container during sync', () => {
		const agents = { 'agent-1': { name: 'Alice', position: [10, 20] as [number, number] } };
		labelSync.updateAgents(agents);

		labelSync.sync();

		expect(worldContainer.toGlobal).toHaveBeenCalled();
	});

	it('should handle agents with no name gracefully', () => {
		labelSync.updateAgents({ 'agent-1': { position: [10, 20] as [number, number] } });

		const label = labelContainer.querySelector('[data-agent-id="agent-1"]');
		expect(label).toBeDefined();
	});

	it('should clear all DOM elements on destroy', () => {
		labelSync.updateAgents({
			'agent-1': { name: 'Alice', position: [10, 20] as [number, number] }
		});

		labelSync.destroy();

		expect(labelContainer.children.length).toBe(0);
	});

	it('should not throw when syncing with no agents', () => {
		expect(() => labelSync.sync()).not.toThrow();
	});
});
