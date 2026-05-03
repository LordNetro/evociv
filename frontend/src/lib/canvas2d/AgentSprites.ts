import { Container, Graphics, Sprite, type Renderer, type Texture } from 'pixi.js';
import { uiStore } from '$lib/stores/uiStore.svelte.js';

export interface AgentState {
	name?: string;
	faction_id?: string;
	position?: [number, number];
	role?: string;
	current_action_emoji?: string;
	is_child?: boolean;
}

export interface FactionState {
	color: string;
}

export class AgentSprites {
	private parent: Container;
	private renderer: Renderer;
	private sprites: Map<string, Sprite> = new Map();
	private badges: Map<string, Graphics> = new Map();
	private agentTexture: Texture | null = null;
	private textureGenerated = false;

	constructor(parent: Container, renderer: Renderer) {
		this.parent = parent;
		this.renderer = renderer;
	}

	get spriteCount(): number {
		return this.sprites.size;
	}

	getSprite(agentId: string): Sprite | undefined {
		return this.sprites.get(agentId);
	}

	/**
	 * Generate the base agent texture (white circle) once.
	 */
	private ensureTexture(): Texture {
		if (!this.agentTexture) {
			const graphics = new Graphics();
			// Draw at 2x resolution (64x64) for smooth anti-aliased edges,
			// then display at 32x32 — PixiJS supersamples for crisp circles
			graphics.circle(32, 32, 28).fill({ color: 0xffffff });
			this.agentTexture = this.renderer.generateTexture(graphics);
			graphics.destroy();
			this.textureGenerated = true;
		}
		return this.agentTexture;
	}

	/**
	 * Parses a hex color string (e.g. "#ff0000") to a number for sprite.tint.
	 */
	private parseColor(color: string): number {
		return parseInt(color.replace('#', ''), 16);
	}

	/**
	 * Create a small gold triangle badge for commanded agents.
	 */
	private createBadge(): Graphics {
		const badge = new Graphics();
		// Draw a small gold triangle pointing up, positioned at top-right of the sprite
		badge.poly([0, 0, 10, 0, 5, 8]).fill({ color: 0xffd700 });
		return badge;
	}

	/**
	 * Sync badges for commanded agents.
	 */
	private syncBadges(commandedAgents: Set<string>): void {
		// Remove badges for agents no longer commanded
		for (const [id, badge] of this.badges) {
			if (!commandedAgents.has(id) || !this.sprites.has(id)) {
				const sprite = this.sprites.get(id);
				if (sprite) {
					sprite.removeChild(badge);
				}
				badge.destroy();
				this.badges.delete(id);
			}
		}

		// Add badges for newly commanded agents
		for (const id of commandedAgents) {
			if (this.sprites.has(id) && !this.badges.has(id)) {
				const sprite = this.sprites.get(id)!;
				const badge = this.createBadge();
				// Position at top-right corner of the sprite
				badge.position.set(sprite.width / 2, -sprite.height / 2);
				sprite.addChild(badge);
				this.badges.set(id, badge);
			}
		}
	}

	/**
	 * Updates agent sprites to match the current agent/faction state.
	 * Creates new sprites, removes dead ones, and recycles existing ones.
	 * @param commandedAgents — Optional set of agent IDs that are currently commanded (show badge)
	 */
	update(agents: Record<string, AgentState>, factions: Record<string, FactionState>, commandedAgents?: Set<string>): void {
		const texture = this.ensureTexture();
		const currentIds = new Set(Object.keys(agents));

		// Remove sprites for agents that no longer exist
		for (const [id, sprite] of this.sprites) {
			if (!currentIds.has(id)) {
				this.parent.removeChild(sprite);
				sprite.destroy();
				this.sprites.delete(id);
			}
		}

		// Create or update sprites for current agents
		for (const [id, agent] of Object.entries(agents)) {
			let sprite = this.sprites.get(id);

			if (!sprite) {
				sprite = new Sprite(texture);
				sprite.anchor.set(0.5);
				// Texture is 64x64, display at 32x32 for smooth anti-aliased edges
				sprite.width = 32;
				sprite.height = 32;
				sprite.eventMode = 'static';
				sprite.cursor = 'pointer';

				// Click handler → uiStore.selectAgent
				sprite.on('pointerdown', () => {
					uiStore.selectAgent(id);
				});

				this.sprites.set(id, sprite);
				this.parent.addChild(sprite);
			}

			// Apply faction tint
			if (agent.faction_id && factions[agent.faction_id]) {
				sprite.tint = this.parseColor(factions[agent.faction_id].color);
			} else {
				sprite.tint = 0xcccccc; // Default gray for no faction
			}
		}

		// Sync command badges (add/remove as needed)
		if (commandedAgents) {
			this.syncBadges(commandedAgents);
		}
	}

	/**
	 * Syncs sprite positions from interpolated agent positions (from canvas2dStore).
	 * Called each frame from the PixiJS Ticker.
	 */
	syncPositions(positions: Record<string, { x: number; y: number }>): void {
		for (const [id, pos] of Object.entries(positions)) {
			const sprite = this.sprites.get(id);
			if (sprite) {
				sprite.position.set(pos.x, pos.y);
			}
		}
	}

	/**
	 * Cleans up all sprites, badges, and the generated texture.
	 */
	destroy(): void {
		for (const [, badge] of this.badges) {
			badge.destroy();
		}
		this.badges.clear();

		for (const [, sprite] of this.sprites) {
			this.parent.removeChild(sprite);
			sprite.destroy();
		}
		this.sprites.clear();

		if (this.agentTexture) {
			this.agentTexture.destroy(true);
			this.agentTexture = null;
		}
	}
}
