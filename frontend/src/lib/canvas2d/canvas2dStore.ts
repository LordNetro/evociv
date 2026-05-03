export type AgentPosition = { x: number; y: number };

export type DialogueBubble = {
	text: string;
	type: 'speech' | 'thought';
	visibleUntil: number;
};

export interface Snapshot {
	agents?: Record<
		string,
		{ position?: [number, number]; current_dialogue?: string; dialogue_type?: string }
	>;
}

class Canvas2DStore {
	agentPositions: Record<string, AgentPosition> = {};
	targetPositions: Record<string, AgentPosition> = {};
	lerpFactor = 0;
	dialogueBubbles: Record<string, DialogueBubble | null> = {};

	/**
	 * Called from $effect when snapshot changes.
	 * @param tileSize — Pixel size of each tile, used to convert grid coords to pixel coords
	 * MUST NOT read `this.agentPositions` to avoid reactive loops
	 * (Svelte 5 tracks all reactive reads inside $effect).
	 */
	updateTargets(snapshot: Snapshot, tileSize: number = 1) {
		if (!snapshot?.agents) return;

		const newTargets: Record<string, AgentPosition> = {};
		const newBubbles: Record<string, DialogueBubble | null> = {};

		for (const [id, agent] of Object.entries(snapshot.agents)) {
			const pos = agent.position as [number, number] | undefined;
			// Validate position: must exist, be non-NaN, non-negative, and within reasonable range
			if (
				pos &&
				typeof pos[0] === 'number' &&
				typeof pos[1] === 'number' &&
				!isNaN(pos[0]) &&
				!isNaN(pos[1]) &&
				pos[0] >= 0 &&
				pos[1] >= 0 &&
				pos[0] < 1000 &&
				pos[1] < 1000
			) {
				newTargets[id] = { x: (pos[0] + 0.5) * tileSize, y: (pos[1] + 0.5) * tileSize };
			}

			if (agent.current_dialogue) {
				const duration = agent.dialogue_type === 'thought' ? 5000 : 3000;
				newBubbles[id] = {
					text: agent.current_dialogue,
					type: agent.dialogue_type === 'thought' ? 'thought' : 'speech',
					visibleUntil: Date.now() + duration
				};
			} else {
				newBubbles[id] = null;
			}
		}

		this.targetPositions = newTargets;
		this.dialogueBubbles = newBubbles;
		this.lerpFactor = 0;
	}

	/**
	 * Called from PixiJS Ticker every frame.
	 * Reads and writes agentPositions freely — no reactive cycle.
	 */
	tick(delta: number) {
		const speed = Math.min(delta * 10, 1);
		this.lerpFactor = Math.min(this.lerpFactor + speed, 1);

		const nextPositions: Record<string, AgentPosition> = {};
		for (const [id, target] of Object.entries(this.targetPositions)) {
			const current = this.agentPositions[id];
			if (!current) {
				// New agent: snap to target
				nextPositions[id] = { x: target.x, y: target.y };
			} else {
				nextPositions[id] = {
					x: current.x + (target.x - current.x) * speed,
					y: current.y + (target.y - current.y) * speed
				};
			}
		}
		// Dead agents are naturally removed — we only iterate targetPositions
		this.agentPositions = nextPositions;

		// Expire old dialogue bubbles
		const now = Date.now();
		for (const [id, bubble] of Object.entries(this.dialogueBubbles)) {
			if (bubble && now > bubble.visibleUntil) {
				this.dialogueBubbles[id] = null;
			}
		}
	}
}

export const canvas2dStore = new Canvas2DStore();
