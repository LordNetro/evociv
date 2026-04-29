export type AgentPosition = { x: number; y: number };

interface Snapshot {
	agents?: Record<string, { position?: [number, number] }>;
}

class Canvas3DStore {
	agentPositions = $state<Record<string, AgentPosition>>({});
	targetPositions = $state<Record<string, AgentPosition>>({});
	lerpFactor = $state(0);

	/**
	 * Called from $effect when snapshot changes.
	 * MUST NOT read `this.agentPositions` to avoid reactive loops
	 * (Svelte 5 tracks all reactive reads inside $effect).
	 */
	updateTargets(snapshot: Snapshot) {
		if (!snapshot?.agents) return;

		const newTargets: Record<string, AgentPosition> = {};
		for (const [id, agent] of Object.entries(snapshot.agents)) {
			const pos = agent.position as [number, number] | undefined;
			if (pos) {
				newTargets[id] = { x: pos[0], y: pos[1] };
			}
		}

		this.targetPositions = newTargets;
		this.lerpFactor = 0;
	}

	/**
	 * Called from useTask every frame (NOT from $effect).
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
	}
}

export const canvas3dStore = new Canvas3DStore();
