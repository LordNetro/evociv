import { Container, Graphics } from 'pixi.js';

/**
 * Animated selection highlight ring drawn via PIXI.Graphics.
 * When an agent is selected, a pulsing circle appears around their position.
 * The ring pulses using a sine wave on scale.
 */
export class OverlayLayer {
	private container: Container;
	private graphics: Graphics;
	private _targetAgentId: string | null = null;
	private animationPhase = 0;
	private readonly RING_RADIUS = 12;
	private ringColor = 0x00ff88;
	private readonly RING_ALPHA = 0.7;
	private readonly PULSE_SPEED = 0.05;
	private readonly MIN_SCALE = 0.85;
	private readonly MAX_SCALE = 1.15;
	private destroyed = false;

	constructor(container: Container) {
		this.container = container;
		this.graphics = new Graphics();
		this.graphics.alpha = 0; // Start invisible
		this.container.addChild(this.graphics);
	}

	/**
	 * Returns the currently targeted agent ID, or null if none.
	 */
	getTargetAgentId(): string | null {
		return this._targetAgentId;
	}

	/**
	 * Updates the ring color. The change takes effect on the next setTarget() call.
	 * @param color — The new color as a 0xRRGGBB number (e.g., 0xffd700 for gold)
	 */
	setRingColor(color: number): void {
		this.ringColor = color;
		// If we have an active target, redraw immediately with the new color
		if (this._targetAgentId !== null) {
			this.graphics.clear();
			this.graphics.circle(0, 0, this.RING_RADIUS);
			this.graphics.stroke({
				color: this.ringColor,
				width: 2,
				alpha: 1
			});
		}
	}

	/**
	 * Sets or clears the selected target.
	 * @param agentId — The agent to highlight, or null to hide
	 * @param x — World X position of the agent
	 * @param y — World Y position of the agent
	 */
	setTarget(agentId: string | null, x: number, y: number): void {
		this._targetAgentId = agentId;

		if (agentId === null) {
			this.graphics.alpha = 0;
			return;
		}

		this.graphics.position.set(x, y);
		this.graphics.alpha = this.RING_ALPHA;
		this.graphics.clear();

		// Draw a ring (circle with no fill, only stroke)
		this.graphics.circle(0, 0, this.RING_RADIUS);
		this.graphics.stroke({
			color: this.ringColor,
			width: 2,
			alpha: 1
		});
	}

	/**
	 * Updates the ring position to follow the agent each frame.
	 * Called from the Ticker — does NOT clear/redraw the graphics.
	 */
	setPosition(x: number, y: number): void {
		if (this._targetAgentId === null || this.destroyed) return;
		this.graphics.position.set(x, y);
	}

	/**
	 * Called every frame from the PixiJS Ticker. Animates the pulsing ring
	 * and follows the selected agent's current interpolated position.
	 * @param delta — PixiJS ticker delta time
	 */
	update(delta: number): void {
		if (this._targetAgentId === null || this.destroyed) return;

		this.animationPhase += delta * this.PULSE_SPEED;

		// Sine wave pulsing between MIN_SCALE and MAX_SCALE
		const pulse =
			this.MIN_SCALE +
			(this.MAX_SCALE - this.MIN_SCALE) * (Math.sin(this.animationPhase) * 0.5 + 0.5);

		this.graphics.scale.set(pulse, pulse);
	}

	/**
	 * Removes the graphics from the container and cleans up.
	 */
	destroy(): void {
		this.destroyed = true;
		this.container.removeChild(this.graphics);
		this.graphics.destroy();
	}
}
