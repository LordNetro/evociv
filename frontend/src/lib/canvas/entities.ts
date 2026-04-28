export interface AgentRenderData {
	id: string;
	/** Current interpolated tile X */
	tileX: number;
	/** Current interpolated tile Y */
	tileY: number;
	/** Target tile X from server */
	targetX: number;
	/** Target tile Y from server */
	targetY: number;
	role: string;
	emoji: string;
	hunger: number;
	thirst: number;
	/** Name for display */
	name: string;
}

const ROLE_COLORS: Record<string, string> = {
	gatherer: '#4CAF50',
	builder: '#FF9800',
	scout: '#2196F3',
	warrior: '#F44336'
};

const RADIUS = 10;

export class Entities {
	private ctx: CanvasRenderingContext2D;
	private agents: Map<string, AgentRenderData> = new Map();
	private tileSize: number;

	constructor(ctx: CanvasRenderingContext2D, tileSize: number = 32) {
		this.ctx = ctx;
		this.tileSize = tileSize;
	}

	/** Tile coords → pixel center of tile */
	private toPx(tx: number, ty: number): { x: number; y: number } {
		return { x: tx * this.tileSize + this.tileSize / 2, y: ty * this.tileSize + this.tileSize / 2 };
	}

	draw(dt: number): void {
		for (const a of this.agents.values()) {
			// Smooth interpolation toward target
			const speed = Math.min(dt * 10, 1);
			a.tileX += (a.targetX - a.tileX) * speed;
			a.tileY += (a.targetY - a.tileY) * speed;

			const { x: px, y: py } = this.toPx(a.tileX, a.tileY);
			const color = ROLE_COLORS[a.role] || '#999';

			// Shadow
			this.ctx.beginPath();
			this.ctx.arc(px + 1.5, py + 2, RADIUS, 0, Math.PI * 2);
			this.ctx.fillStyle = 'rgba(0,0,0,0.25)';
			this.ctx.fill();

			// Body circle
			this.ctx.beginPath();
			this.ctx.arc(px, py, RADIUS, 0, Math.PI * 2);
			this.ctx.fillStyle = color;
			this.ctx.fill();
			this.ctx.strokeStyle = 'rgba(0,0,0,0.4)';
			this.ctx.lineWidth = 1.5;
			this.ctx.stroke();

			// Name label
			this.ctx.fillStyle = '#fff';
			this.ctx.font = 'bold 10px sans-serif';
			this.ctx.textAlign = 'center';
			this.ctx.textBaseline = 'middle';
			this.ctx.fillText(a.name.charAt(0), px, py + 1);

			// Hunger bar
			if (a.hunger > 5) {
				const w = 16;
				this.ctx.fillStyle = 'rgba(255,50,50,0.5)';
				this.ctx.fillRect(px - w / 2, py - RADIUS - 6, w * Math.min(a.hunger / 100, 1), 2);
			}

			// Action emoji
			if (a.emoji) {
				this.ctx.font = '11px serif';
				this.ctx.textAlign = 'center';
				this.ctx.textBaseline = 'bottom';
				this.ctx.fillText(a.emoji, px, py - RADIUS - 8);
			}
		}
	}

	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	updateFromSnapshot(data: any): void {
		if (!data?.agents) return;

		// Remove dead agents (explicitly from removed_agents list)
		if (data.removed_agents) {
			for (const id of data.removed_agents) {
				this.agents.delete(id);
			}
		}

		// Remove agents that are no longer in the snapshot at all
		// (they died but removed_agents was already cleared in a previous tick)
		const liveIds = new Set(Object.keys(data.agents));
		for (const id of this.agents.keys()) {
			if (!liveIds.has(id)) {
				this.agents.delete(id);
			}
		}

		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		for (const [id, state] of Object.entries(data.agents) as [string, any][]) {
			let a = this.agents.get(id);
			if (!a) {
				a = {
					id,
					tileX: 0,
					tileY: 0,
					targetX: 0,
					targetY: 0,
					role: '',
					emoji: '',
					hunger: 0,
					thirst: 0,
					name: state.name ?? id
				};
				this.agents.set(id, a);
			}
			a.targetX = state.position?.[0] ?? a.targetX;
			a.targetY = state.position?.[1] ?? a.targetY;
			a.role = state.role ?? a.role;
			a.emoji = state.current_action_emoji ?? a.emoji;
			a.hunger = state.hunger ?? a.hunger;
			a.thirst = state.thirst ?? a.thirst;
			a.name = state.name ?? a.name;
		}
	}

	/** Find agent by pixel position (world pixels) */
	getAgentAt(px: number, py: number): string | null {
		const threshold = RADIUS + 4;
		for (const a of this.agents.values()) {
			const pos = this.toPx(a.tileX, a.tileY);
			const dx = pos.x - px;
			const dy = pos.y - py;
			if (dx * dx + dy * dy < threshold * threshold) {
				return a.id;
			}
		}
		return null;
	}

	/** Center of all agents in pixel coords, or null if none */
	getCenter(): { x: number; y: number } | null {
		if (this.agents.size === 0) return null;
		let sx = 0,
			sy = 0;
		for (const a of this.agents.values()) {
			sx += a.tileX;
			sy += a.tileY;
		}
		return this.toPx(sx / this.agents.size, sy / this.agents.size);
	}

	destroy(): void {
		this.agents.clear();
	}
}
