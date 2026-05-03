import { Container, Graphics, Sprite, type Renderer, type Texture } from 'pixi.js';

/**
 * A single harvest burst particle with velocity, lifetime, and fade.
 */
interface BurstParticle {
	sprite: Sprite;
	vx: number;
	vy: number;
	lifetime: number;
	maxLifetime: number;
}

/**
 * Manages visual effects: harvest burst particles, ambient dust, and weather particles.
 * Added to the effectsContainer in Canvas2D.svelte.
 */
export class EffectsLayer {
	private container: Container;
	private renderer: Renderer;
	private burstParticles: BurstParticle[] = [];
	private ambientParticles: Sprite[] = [];
	private weatherParticles: Sprite[] = [];
	private ambientDrift: Map<Sprite, { driftX: number; driftY: number }> = new Map();
	private weatherDrift: Map<Sprite, { fallSpeed: number; driftX: number }> = new Map();
	private burstTexture: Texture | null = null;
	private dustTexture: Texture | null = null;
	private weatherActive = false;

	// Resource type → tint color mapping
	private readonly RESOURCE_COLORS: Record<string, number> = {
		berries: 0xdc143c,
		trees: 0x228b22,
		iron_ore: 0xcd853f,
		stone: 0x808080,
		copper_ore: 0xb87333,
		gold_ore: 0xffd700,
		coal: 0x36454f,
		clay: 0xcc5533,
		flint: 0x4a4a4a,
		water: 0x4169e1,
		harvest: 0xffaa00
	};

	private readonly AMBIENT_COUNT = 0; // Disabled — was 300 but user found them distracting
	private readonly WEATHER_COUNT = 500;
	private readonly BURST_COUNT = 15;
	private readonly BURST_LIFETIME = 500; // ms (at ~60fps, 1 delta ≈ 16ms, so ~31 ticks)
	private readonly BURST_SPEED = 60; // pixels per second
	private destroyed = false;

	constructor(container: Container, renderer: Renderer) {
		this.container = container;
		this.renderer = renderer;
		this.generateTextures();
		this.initAmbientDust();
	}

	/**
	 * Generates shared textures for particles.
	 */
	private generateTextures(): void {
		// Burst particle: draw at 2x for smooth edges
		const burstGraphic = new Graphics();
		burstGraphic.circle(8, 8, 7).fill({ color: 0xffffff });
		this.burstTexture = this.renderer.generateTexture(burstGraphic);
		burstGraphic.destroy();

		// Dust particle: tiny dot at 2x
		const dustGraphic = new Graphics();
		dustGraphic.circle(4, 4, 3).fill({ color: 0xffffff });
		this.dustTexture = this.renderer.generateTexture(dustGraphic);
		dustGraphic.destroy();
	}

	/**
	 * Creates ambient dust particles that float gently.
	 */
	private initAmbientDust(): void {
		if (!this.dustTexture) return;

		for (let i = 0; i < this.AMBIENT_COUNT; i++) {
			const sprite = new Sprite(this.dustTexture);
			sprite.position.set(Math.random() * 800 - 100, Math.random() * 800 - 100);
			sprite.alpha = 0.1 + Math.random() * 0.2;
			sprite.scale.set(0.5 + Math.random() * 0.5);
			this.ambientDrift.set(sprite, {
				driftX: (Math.random() - 0.5) * 0.3,
				driftY: (Math.random() - 0.5) * 0.2
			});

			this.ambientParticles.push(sprite);
			this.container.addChild(sprite);
		}
	}

	/**
	 * Spawns a harvest burst at the given world position.
	 * @param x — World X position
	 * @param y — World Y position
	 * @param type — Resource type (used for color tinting)
	 */
	spawnHarvestBurst(x: number, y: number, type: string): void {
		if (this.destroyed || !this.burstTexture) return;

		const color = this.RESOURCE_COLORS[type] ?? 0xffaa00;

		for (let i = 0; i < this.BURST_COUNT; i++) {
			const sprite = new Sprite(this.burstTexture);
			sprite.position.set(x, y);
			sprite.anchor.set(0.5);
			sprite.tint = color;
			sprite.scale.set(0.8 + Math.random() * 0.6);

			// Random velocity outward
			const angle = (Math.PI * 2 * i) / this.BURST_COUNT + (Math.random() - 0.5) * 0.5;
			const speed = this.BURST_SPEED * (0.5 + Math.random() * 0.8);

			this.container.addChild(sprite);

			this.burstParticles.push({
				sprite,
				vx: Math.cos(angle) * speed,
				vy: Math.sin(angle) * speed,
				lifetime: 0,
				maxLifetime: this.BURST_LIFETIME
			});
		}
	}

	/**
	 * Returns the number of active burst particles.
	 */
	getBurstParticleCount(): number {
		return this.burstParticles.length;
	}

	/**
	 * Enables or disables weather effects (rain/snow).
	 * @param active — Whether weather particles should be shown
	 * @param type — 'rain' or 'snow'
	 */
	setWeather(active: boolean, type: 'rain' | 'snow' = 'rain'): void {
		this.weatherActive = active;

		if (active && this.weatherParticles.length === 0 && this.dustTexture) {
			const isSnow = type === 'snow';
			for (let i = 0; i < this.WEATHER_COUNT; i++) {
				const sprite = new Sprite(this.dustTexture);
				sprite.position.set(Math.random() * 900, Math.random() * 900 - 100);
				sprite.alpha = isSnow ? 0.6 : 0.3;
				sprite.tint = isSnow ? 0xffffff : 0x8888ff;
				sprite.scale.set(isSnow ? 1.5 : 0.8);

				this.weatherDrift.set(sprite, {
					fallSpeed: isSnow ? 1 + Math.random() * 0.5 : 3 + Math.random() * 2,
					driftX: isSnow ? (Math.random() - 0.5) * 0.5 : (Math.random() - 0.5) * 1.5
				});

				this.weatherParticles.push(sprite);
				this.container.addChild(sprite);
			}
		} else if (!active) {
			this.clearWeather();
		}
	}

	/**
	 * Called every frame from the PixiJS Ticker.
	 * Updates burst particles (animate → fade → remove).
	 * Drifts ambient dust.
	 * Falls weather particles.
	 * @param delta — PixiJS ticker delta time (1 = 16.67ms at 60fps)
	 */
	update(delta: number): void {
		if (this.destroyed) return;

		this.updateBursts(delta);
		this.updateAmbientDust(delta);
		this.updateWeather(delta);
	}

	/**
	 * Updates harvest burst particles: move outward, fade out, remove expired.
	 */
	private updateBursts(delta: number): void {
		const dt = delta * 16; // Convert ticker delta to approximate ms
		const toRemove: number[] = [];

		for (let i = 0; i < this.burstParticles.length; i++) {
			const p = this.burstParticles[i];
			p.lifetime += dt;

			if (p.lifetime >= p.maxLifetime) {
				toRemove.push(i);
				continue;
			}

			// Move particle
			p.sprite.position.x += (p.vx * delta) / 60;
			p.sprite.position.y += (p.vy * delta) / 60;

			// Fade out (also scale down slightly)
			const progress = p.lifetime / p.maxLifetime;
			p.sprite.alpha = 1 - progress;
			const scale = 1 - progress * 0.5;
			p.sprite.scale.set(scale, scale);
		}

		// Remove expired (reverse order to maintain indices)
		for (let i = toRemove.length - 1; i >= 0; i--) {
			const idx = toRemove[i];
			const p = this.burstParticles[idx];
			this.container.removeChild(p.sprite);
			p.sprite.destroy();
			this.burstParticles.splice(idx, 1);
		}
	}

	/**
	 * Gently drifts ambient dust particles.
	 */
	private updateAmbientDust(delta: number): void {
		for (const sprite of this.ambientParticles) {
			const drift = this.ambientDrift.get(sprite);
			if (!drift) continue;
			sprite.position.x += drift.driftX * delta;
			sprite.position.y += drift.driftY * delta;

			// Wrap around screen edges
			if (sprite.position.x > 900) sprite.position.x = -100;
			if (sprite.position.x < -100) sprite.position.x = 900;
			if (sprite.position.y > 900) sprite.position.y = -100;
			if (sprite.position.y < -100) sprite.position.y = 900;
		}
	}

	/**
	 * Falls weather particles downward, wrapping at bottom.
	 */
	private updateWeather(delta: number): void {
		if (!this.weatherActive) return;

		for (const sprite of this.weatherParticles) {
			const drift = this.weatherDrift.get(sprite);
			if (!drift) continue;
			sprite.position.y += drift.fallSpeed * delta;
			sprite.position.x += drift.driftX * delta;

			// Reset at bottom
			if (sprite.position.y > 900) {
				sprite.position.y = -50;
				sprite.position.x = Math.random() * 900;
			}
			if (sprite.position.x > 950) sprite.position.x = -50;
			if (sprite.position.x < -50) sprite.position.x = 950;
		}
	}

	/**
	 * Removes all weather particles.
	 */
	private clearWeather(): void {
		for (const sprite of this.weatherParticles) {
			this.container.removeChild(sprite);
			sprite.destroy();
		}
		this.weatherParticles = [];
	}

	/**
	 * Cleans up all particles and textures.
	 */
	destroy(): void {
		this.destroyed = true;

		// Burst particles
		for (const p of this.burstParticles) {
			this.container.removeChild(p.sprite);
			p.sprite.destroy();
		}
		this.burstParticles = [];

		// Ambient dust
		for (const sprite of this.ambientParticles) {
			this.container.removeChild(sprite);
			sprite.destroy();
		}
		this.ambientParticles = [];

		// Weather particles
		this.clearWeather();

		// Textures
		if (this.burstTexture) {
			this.burstTexture.destroy(true);
			this.burstTexture = null;
		}
		if (this.dustTexture) {
			this.dustTexture.destroy(true);
			this.dustTexture = null;
		}
	}
}
