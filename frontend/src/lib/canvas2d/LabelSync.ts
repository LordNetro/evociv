import type { Container, Point } from 'pixi.js';

/**
 * Label descriptor for an agent label DOM element.
 */
interface LabelEntry {
	el: HTMLElement;
	bubbleEl: HTMLElement | null;
	agentId: string;
	lastPosition: { x: number; y: number };
	lastBubble: string | null;
}

/**
 * A dialogue bubble from the store.
 */
interface DialogueBubbleData {
	text: string;
	type: 'speech' | 'thought';
	visibleUntil: number;
}

/**
 * Synchronizes DOM label positions with agent sprite world positions.
 * Uses worldContainer.toGlobal() to convert agent positions to screen coordinates,
 * then updates each label's CSS transform for pixel-perfect positioning.
 *
 * Also renders speech/thought bubbles above agent labels when agents have active dialogue.
 *
 * Separated from the render Ticker to avoid DOM jitter — runs once per animation frame
 * via requestAnimationFrame.
 */
export class LabelSync {
	private worldContainer: Container;
	private labelContainer: HTMLElement;
	private labels: Map<string, LabelEntry> = new Map();
	private rafId: number | null = null;
	private running = false;
	private bubbles: Record<string, DialogueBubbleData | null> = {};

	constructor(worldContainer: Container, labelContainer: HTMLElement) {
		this.worldContainer = worldContainer;
		this.labelContainer = labelContainer;
	}

	/**
	 * Updates the dialogue bubble data for speech bubble rendering.
	 * Called each frame or when dialogue changes.
	 */
	updateBubbles(bubbles: Record<string, DialogueBubbleData | null>): void {
		this.bubbles = bubbles;
	}

	/**
	 * Creates or updates DOM label elements for the given agents.
	 * Removes labels for agents that no longer exist.
	 * @param agents — Record of agent id → agent data with name and position
	 */
	updateAgents(agents: Record<string, { name?: string; position?: [number, number] }>): void {
		const currentIds = new Set(Object.keys(agents));

		// Remove labels for agents no longer present
		for (const [id, entry] of this.labels) {
			if (!currentIds.has(id)) {
				if (entry.bubbleEl) {
					this.labelContainer.removeChild(entry.bubbleEl);
				}
				this.labelContainer.removeChild(entry.el);
				this.labels.delete(id);
			}
		}

		// Create or update labels
		for (const [id, agent] of Object.entries(agents)) {
			let entry = this.labels.get(id);

			if (!entry) {
				const el = document.createElement('div');
				el.setAttribute('data-agent-id', id);
				el.className = 'agent-label';
				el.style.position = 'absolute';
				el.style.pointerEvents = 'none';
				el.style.transform = 'translate(-50%, -100%)';
				el.style.whiteSpace = 'nowrap';
				el.style.fontSize = '11px';
				el.style.color = '#fff';
				el.style.textShadow = '0 1px 3px rgba(0,0,0,0.8)';
				el.style.fontFamily = 'sans-serif';

				this.labelContainer.appendChild(el);

				entry = {
					el,
					bubbleEl: null,
					agentId: id,
					lastPosition: { x: 0, y: 0 },
					lastBubble: null
				};
				this.labels.set(id, entry);
			}

			// Update label text
			entry.el.textContent = agent.name ?? id;

			// Render speech/thought bubble
			const bubbleData = this.bubbles[id];
			if (bubbleData && bubbleData.text) {
				if (!entry.bubbleEl) {
					const bubbleEl = document.createElement('div');
					bubbleEl.className = 'agent-speech-bubble';
					bubbleEl.style.position = 'absolute';
					bubbleEl.style.pointerEvents = 'none';
					bubbleEl.style.transform = 'translate(-50%, -100%)';
					bubbleEl.style.whiteSpace = 'nowrap';
					bubbleEl.style.fontSize = '10px';
					bubbleEl.style.color = '#fff';
					bubbleEl.style.background =
						bubbleData.type === 'thought' ? 'rgba(100,100,100,0.7)' : 'rgba(0,0,0,0.75)';
					bubbleEl.style.borderRadius = '8px';
					bubbleEl.style.padding = '2px 8px';
					bubbleEl.style.marginTop = '-14px';
					bubbleEl.style.fontFamily = 'sans-serif';
					bubbleEl.style.textShadow = '0 1px 2px rgba(0,0,0,0.8)';
					bubbleEl.style.border =
						bubbleData.type === 'thought'
							? '1px dashed rgba(255,255,255,0.3)'
							: '1px solid rgba(255,255,255,0.15)';

					this.labelContainer.appendChild(bubbleEl);
					entry.bubbleEl = bubbleEl;
				}
				entry.bubbleEl.textContent = bubbleData.text;
				entry.lastBubble = bubbleData.text;
			} else if (entry.bubbleEl) {
				this.labelContainer.removeChild(entry.bubbleEl);
				entry.bubbleEl = null;
				entry.lastBubble = null;
			}

			// Store position for sync
			if (agent.position) {
				entry.lastPosition = { x: agent.position[0], y: agent.position[1] };
			}
		}
	}

	/**
	 * Starts the RAF sync loop.
	 */
	start(): void {
		if (this.running) return;
		this.running = true;
		this.syncLoop();
	}

	/**
	 * Stops the RAF sync loop.
	 */
	stop(): void {
		this.running = false;
		if (this.rafId !== null) {
			cancelAnimationFrame(this.rafId);
			this.rafId = null;
		}
	}

	/**
	 * Single sync pass: converts each agent's world position to screen
	 * coordinates and updates the DOM label and speech bubble positions.
	 *
	 * This is called from the RAF loop but can also be called externally
	 * for manual sync.
	 */
	sync(): void {
		for (const [, entry] of this.labels) {
			const globalPos = this.worldContainer.toGlobal(entry.lastPosition as unknown as Point);
			const labelY = globalPos.y - 16; // offset above the agent sprite
			entry.el.style.transform = `translate(-50%, -100%) translate(${globalPos.x}px, ${labelY}px)`;

			if (entry.bubbleEl) {
				const bubbleY = labelY - 4; // slightly above the name label
				entry.bubbleEl.style.transform = `translate(-50%, -100%) translate(${globalPos.x}px, ${bubbleY}px)`;
			}
		}
	}

	/**
	 * The RAF loop: calls sync() each frame while running.
	 */
	private syncLoop(): void {
		if (!this.running) return;

		this.sync();
		this.rafId = requestAnimationFrame(() => this.syncLoop());
	}

	/**
	 * Stops the RAF loop and removes all label and bubble DOM elements.
	 */
	destroy(): void {
		this.stop();

		for (const [, entry] of this.labels) {
			if (entry.bubbleEl) {
				this.labelContainer.removeChild(entry.bubbleEl);
			}
			this.labelContainer.removeChild(entry.el);
		}
		this.labels.clear();
	}
}
