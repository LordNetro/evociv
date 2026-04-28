import { Camera } from './camera';

export interface TileData {
  x: number;
  y: number;
  resourceType: string | null;
  amount: number;
}

export class Grid {
  private ctx: CanvasRenderingContext2D;
  private tileSize: number;
  private width: number;
  private height: number;
  private tiles: Map<string, TileData> = new Map();
  private camera: Camera;
  private vw = 0;
  private vh = 0;

  constructor(ctx: CanvasRenderingContext2D, camera: Camera, config: { tileSize: number; gridWidth: number; gridHeight: number }) {
    this.ctx = ctx;
    this.camera = camera;
    this.tileSize = config.tileSize;
    this.width = config.gridWidth;
    this.height = config.gridHeight;
  }

  /** Must be called on resize to update viewport dimensions */
  setViewport(vw: number, vh: number): void {
    this.vw = vw;
    this.vh = vh;
  }

  draw(): void {
    const vis = this.camera.visibleRect(this.vw, this.vh);
    const ts = this.tileSize;

    // Only iterate over tiles that are visible in the viewport
    const startX = Math.max(0, Math.floor(vis.left / ts));
    const startY = Math.max(0, Math.floor(vis.top / ts));
    const endX = Math.min(this.width, Math.ceil(vis.right / ts));
    const endY = Math.min(this.height, Math.ceil(vis.bottom / ts));

    for (let y = startY; y < endY; y++) {
      for (let x = startX; x < endX; x++) {
        const px = x * ts;
        const py = y * ts;
        const key = `${x},${y}`;
        const tile = this.tiles.get(key);

        // Tile background
        this.ctx.fillStyle = tile?.resourceType ? '#3d2b1f' : '#2d1b0e';
        this.ctx.fillRect(px, py, ts, ts);

        // Grid line
        this.ctx.strokeStyle = 'rgba(255,255,255,0.04)';
        this.ctx.lineWidth = 0.5;
        this.ctx.strokeRect(px, py, ts, ts);

        // Resource
        if (tile?.resourceType) {
          this.drawResource(tile, px, py, ts);
        }
      }
    }
  }

  private drawResource(tile: TileData, px: number, py: number, ts: number): void {
    const cx = px + ts / 2;
    const cy = py + ts / 2;
    const s = ts * 0.25;

    switch (tile.resourceType) {
      case 'tree':
        this.ctx.fillStyle = '#2e7d32';
        this.ctx.beginPath();
        this.ctx.arc(cx, cy - s * 0.2, s * 1.2, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.fillStyle = '#5d4037';
        this.ctx.fillRect(cx - s * 0.2, cy - s * 0.1, s * 0.4, s * 0.8);
        break;
      case 'water':
        this.ctx.fillStyle = '#1565c0';
        this.ctx.beginPath();
        this.ctx.arc(cx, cy, s, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.fillStyle = 'rgba(255,255,255,0.15)';
        this.ctx.beginPath();
        this.ctx.arc(cx - s * 0.2, cy - s * 0.2, s * 0.3, 0, Math.PI * 2);
        this.ctx.fill();
        break;
      case 'berries':
        this.ctx.fillStyle = '#c62828';
        for (let i = 0; i < 3; i++) {
          const angle = (i / 3) * Math.PI * 2;
          this.ctx.beginPath();
          this.ctx.arc(cx + Math.cos(angle) * s * 0.4, cy + Math.sin(angle) * s * 0.4, s * 0.25, 0, Math.PI * 2);
          this.ctx.fill();
        }
        this.ctx.fillStyle = '#2e7d32';
        this.ctx.fillRect(cx - s * 0.08, cy - s * 0.6, s * 0.16, s * 0.5);
        break;
      case 'stone':
        this.ctx.fillStyle = '#757575';
        this.ctx.beginPath();
        this.ctx.ellipse(cx, cy, s, s * 0.7, 0, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.fillStyle = '#9e9e9e';
        this.ctx.beginPath();
        this.ctx.ellipse(cx - s * 0.2, cy - s * 0.2, s * 0.3, s * 0.25, 0, 0, Math.PI * 2);
        this.ctx.fill();
        break;
    }
  }

  updateTiles(tiles: TileData[]): void {
    for (const tile of tiles) {
      this.tiles.set(`${tile.x},${tile.y}`, tile);
    }
  }

  destroy(): void {
    this.tiles.clear();
  }
}
