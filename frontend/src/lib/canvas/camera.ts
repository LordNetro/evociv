/** Simple 2D camera with pan and zoom. */
export class Camera {
  /** Camera position in world pixels (top-left of viewport) */
  x = 0;
  y = 0;

  /** Zoom level: 1 = 1 pixel = 1 pixel, 2 = 2x magnification */
  private _zoom = 1;

  get zoom(): number {
    return this._zoom;
  }

  set zoom(v: number) {
    this._zoom = Math.max(0.05, Math.min(20, v));
  }

  /** Move camera so (wx, wy) in world pixels is at the center of the viewport */
  centerOn(wx: number, wy: number, vw: number, vh: number): void {
    this.x = wx - vw / (2 * this._zoom);
    this.y = wy - vh / (2 * this._zoom);
  }

  /** Fit the given world rect into the viewport */
  fit(worldW: number, worldH: number, vw: number, vh: number, margin = 0.05): void {
    const scaleX = vw / worldW;
    const scaleY = vh / worldH;
    this._zoom = Math.min(scaleX, scaleY) * (1 - margin);
    this.x = 0;
    this.y = 0;
  }

  /** Convert screen (canvas-relative) coords → world pixel coords */
  screenToWorld(sx: number, sy: number): { x: number; y: number } {
    return { x: sx / this._zoom + this.x, y: sy / this._zoom + this.y };
  }

  /** Apply camera transform */
  apply(ctx: CanvasRenderingContext2D): void {
    ctx.save();
    ctx.translate(-this.x * this._zoom, -this.y * this._zoom);
    ctx.scale(this._zoom, this._zoom);
  }

  /** Restore after camera transform */
  restore(ctx: CanvasRenderingContext2D): void {
    ctx.restore();
  }

  /** Get the visible world rect in world pixels */
  visibleRect(vw: number, vh: number): { left: number; top: number; right: number; bottom: number } {
    return {
      left: this.x,
      top: this.y,
      right: this.x + vw / this._zoom,
      bottom: this.y + vh / this._zoom,
    };
  }
}
