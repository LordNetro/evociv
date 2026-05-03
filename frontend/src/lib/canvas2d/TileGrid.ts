import { Container, Graphics, Sprite, type Texture, type Renderer } from 'pixi.js';

export interface ResourceOverlay {
	sprite: Sprite;
	tileX: number;
	tileY: number;
	resourceType: string;
}

export class TileGrid {
	public tileSprites: Sprite[] = [];
	public resourceSprites: ResourceOverlay[] = [];
	public atlas: Texture | null = null;

	private parent: Container;
	private gridSize: number;
	private tileSize: number;

	constructor(parent: Container, gridSize: number, tileSize: number) {
		this.parent = parent;
		this.gridSize = gridSize;
		this.tileSize = tileSize;
	}

	/**
	 * Builds the tile grid: creates a procedural atlas texture,
	 * generates tile sprites, and adds them to the parent container.
	 */
	build(renderer: Renderer): void {
		// Create procedural grass tile texture
		const grassGraphics = new Graphics();
		grassGraphics.rect(0, 0, this.tileSize, this.tileSize).fill({ color: 0x3a5a3a });

		// Add subtle grid lines
		grassGraphics.rect(0, 0, this.tileSize, 1).fill({ color: 0x2d4a2d });
		grassGraphics.rect(0, 0, 1, this.tileSize).fill({ color: 0x2d4a2d });

		this.atlas = renderer.generateTexture(grassGraphics);
		grassGraphics.destroy();

		// Generate tile sprites in row-major order
		for (let row = 0; row < this.gridSize; row++) {
			for (let col = 0; col < this.gridSize; col++) {
				const sprite = new Sprite(this.atlas);
				sprite.position.set(col * this.tileSize, row * this.tileSize);
				sprite.width = this.tileSize;
				sprite.height = this.tileSize;
				this.parent.addChild(sprite);
				this.tileSprites.push(sprite);
			}
		}
	}

	/**
	 * Adds a resource overlay sprite at the given tile position.
	 */
	addResourceOverlay(
		renderer: Renderer,
		tileX: number,
		tileY: number,
		resourceType: string
	): Sprite | null {
		// Map resource types to colors
		const colorMap: Record<string, number> = {
			iron_ore: 0x8b4513,
			trees: 0x228b22,
			water: 0x4169e1,
			stone: 0x808080,
			copper_ore: 0xb87333,
			gold_ore: 0xffd700,
			coal: 0x36454f,
			clay: 0xcc5533,
			berries: 0xdc143c,
			flint: 0x4a4a4a
		};

		const color = colorMap[resourceType] ?? 0xffffff;

		// Draw resource circle at 2x tile resolution for smooth anti-aliased edges
		const resourceGraphic = new Graphics();
		const size = this.tileSize * 2;
		const center = size / 2;
		resourceGraphic.circle(center, center, center * 0.4).fill({ color });

		const texture = renderer.generateTexture(resourceGraphic);
		resourceGraphic.destroy();

		const sprite = new Sprite(texture);
		const halfTile = this.tileSize / 2;
		sprite.position.set(tileX * this.tileSize + halfTile, tileY * this.tileSize + halfTile);
		sprite.anchor.set(0.5);
		sprite.width = this.tileSize * 0.5;
		sprite.height = this.tileSize * 0.5;

		this.parent.addChild(sprite);

		this.resourceSprites.push({ sprite, tileX, tileY, resourceType });

		return sprite;
	}

	/**
	 * Syncs resource overlays from simulation tile data.
	 * Adds new overlays for tiles with resources, removes overlays
	 * for tiles that no longer have resources.
	 * @param tiles — Array of tiles from snapshot, each with x, y, resource_type, amount
	 */
	syncResources(
		renderer: Renderer,
		tiles: Array<{ x: number; y: number; resource_type: string | null; amount: number }>
	): void {
		// Build a set of current resource positions from snapshot
		const currentResources = new Set<string>();
		for (const tile of tiles) {
			if (tile.resource_type && tile.amount > 0) {
				const key = `${tile.x},${tile.y}`;
				currentResources.add(key);

				// Check if overlay already exists at this position
				const exists = this.resourceSprites.some(
					(r) => r.tileX === tile.x && r.tileY === tile.y && r.resourceType === tile.resource_type
				);
				if (!exists) {
					this.addResourceOverlay(renderer, tile.x, tile.y, tile.resource_type);
				}
			}
		}

		// Remove overlays for tiles that no longer have resources
		for (let i = this.resourceSprites.length - 1; i >= 0; i--) {
			const overlay = this.resourceSprites[i];
			const key = `${overlay.tileX},${overlay.tileY}`;
			if (!currentResources.has(key)) {
				this.parent.removeChild(overlay.sprite);
				overlay.sprite.destroy();
				this.resourceSprites.splice(i, 1);
			}
		}
	}

	/**
	 * Removes a resource overlay by tile position.
	 */
	removeResourceOverlay(tileX: number, tileY: number): void {
		const idx = this.resourceSprites.findIndex((r) => r.tileX === tileX && r.tileY === tileY);
		if (idx !== -1) {
			const overlay = this.resourceSprites[idx];
			this.parent.removeChild(overlay.sprite);
			overlay.sprite.destroy();
			this.resourceSprites.splice(idx, 1);
		}
	}

	/**
	 * Cleans up all sprites and textures.
	 */
	destroy(): void {
		for (const sprite of this.tileSprites) {
			this.parent.removeChild(sprite);
			sprite.destroy();
		}
		this.tileSprites = [];

		for (const overlay of this.resourceSprites) {
			this.parent.removeChild(overlay.sprite);
			overlay.sprite.destroy();
		}
		this.resourceSprites = [];

		if (this.atlas) {
			this.atlas.destroy(true);
			this.atlas = null;
		}
	}
}
