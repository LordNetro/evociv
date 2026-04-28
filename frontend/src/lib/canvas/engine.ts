import { Grid } from './grid';
import { Entities } from './entities';
import { Camera } from './camera';

export interface EngineConfig {
  tileSize: number;
  gridWidth: number;
  gridHeight: number;
}

export class Engine {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private grid: Grid;
  private entities: Entities;
  camera: Camera;
  private animFrameId: number | null = null;
  private running = false;
  private lastTime = 0;
  private config: EngineConfig;

  /** Viewport dimensions in screen pixels */
  private vw = 0;
  private vh = 0;

  /** Current fps for debug display */
  fps = 0;
  private frameCount = 0;
  private fpsTimer = 0;

  /** Callback when agent clicked */
  onAgentClick: ((id: string) => void) | null = null;

  constructor(canvas: HTMLCanvasElement, config: EngineConfig) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d')!;
    this.config = config;
    this.camera = new Camera();
    this.grid = new Grid(this.ctx, this.camera, config);
    this.entities = new Entities(this.ctx, config.tileSize);
  }

  /** Call once with final dimensions before start() */
  setSize(w: number, h: number): void {
    this.vw = w;
    this.vh = h;
    this.canvas.width = w;
    this.canvas.height = h;
    this.grid.setViewport(w, h);
    // Fit world view
    const worldPx = this.config.gridWidth * this.config.tileSize;
    const worldPh = this.config.gridHeight * this.config.tileSize;
    this.camera.fit(worldPx, worldPh, w, h);
  }

  start(): void {
    this.running = true;
    this.lastTime = performance.now();
    this.fpsTimer = this.lastTime;
    this.setupInput();
    this.loop(this.lastTime);
  }

  stop(): void {
    this.running = false;
    if (this.animFrameId !== null) {
      cancelAnimationFrame(this.animFrameId);
    }
  }

  private loop = (now: number): void => {
    if (!this.running) return;
    const dt = (now - this.lastTime) / 1000;
    this.lastTime = now;

    // FPS counter
    this.frameCount++;
    if (now - this.fpsTimer > 1000) {
      this.fps = this.frameCount;
      this.frameCount = 0;
      this.fpsTimer = now;
    }

    // Draw
    this.ctx.clearRect(0, 0, this.vw, this.vh);
    this.ctx.fillStyle = '#1a0f0a';
    this.ctx.fillRect(0, 0, this.vw, this.vh);

    this.camera.apply(this.ctx);
    this.grid.draw();
    this.entities.draw(dt);
    this.camera.restore(this.ctx);

    // Debug info
    this.drawDebug();

    this.animFrameId = requestAnimationFrame(this.loop);
  };

  private drawDebug(): void {
    const cam = this.camera;
    const lines = [
      `Zoom: ${cam.zoom.toFixed(2)}x`,
      `Pos: (${cam.x.toFixed(0)}, ${cam.y.toFixed(0)})`,
      `FPS: ${this.fps}`,
      `Agents: ${this.entities['agents'].size}`,
    ];
    this.ctx.fillStyle = 'rgba(0,0,0,0.6)';
    this.ctx.fillRect(this.vw - 140, 4, 136, 14 * lines.length + 8);
    this.ctx.fillStyle = '#0f0';
    this.ctx.font = '11px monospace';
    this.ctx.textAlign = 'left';
    this.ctx.textBaseline = 'top';
    lines.forEach((l, i) => {
      this.ctx.fillText(l, this.vw - 134, 8 + i * 14);
    });
  }

  /** Call from websocket data */
  updateSnapshot(data: unknown): void {
    this.entities.updateFromSnapshot(data);
    this.grid.updateTiles((data as any)?.tiles ?? []);
  }

  // ── Input handling ──────────────────────────────────

  private setupInput(): void {
    let drag = { active: false, sx: 0, sy: 0, camX: 0, camY: 0, lx: 0, ly: 0 };

    this.canvas.addEventListener('mousedown', (e) => {
      drag.active = true;
      drag.sx = e.clientX;
      drag.sy = e.clientY;
      drag.camX = this.camera.x;
      drag.camY = this.camera.y;
      drag.lx = e.clientX;
      drag.ly = e.clientY;
    });

    window.addEventListener('mousemove', (e) => {
      if (!drag.active) return;
      drag.lx = e.clientX;
      drag.ly = e.clientY;
      const dx = (e.clientX - drag.sx) / this.camera.zoom;
      const dy = (e.clientY - drag.sy) / this.camera.zoom;
      this.camera.x = drag.camX - dx;
      this.camera.y = drag.camY - dy;
    });

    window.addEventListener('mouseup', (e) => {
      if (!drag.active) return;
      drag.active = false;
      const dist = Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy);
      if (dist < 4 && this.onAgentClick) {
        const rect = this.canvas.getBoundingClientRect();
        const wp = this.camera.screenToWorld(e.clientX - rect.left, e.clientY - rect.top);
        const id = this.entities.getAgentAt(wp.x, wp.y);
        if (id) this.onAgentClick(id);
      }
    });

    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const rect = this.canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      // Zoom toward mouse
      const before = this.camera.screenToWorld(mx, my);
      this.camera.zoom *= e.deltaY > 0 ? 1 / 1.12 : 1.12;
      const after = this.camera.screenToWorld(mx, my);
      this.camera.x += before.x - after.x;
      this.camera.y += before.y - after.y;
    }, { passive: false });
  }

  destroy(): void {
    this.stop();
    this.grid.destroy();
    this.entities.destroy();
  }
}
