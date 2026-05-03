import { ColorMatrixFilter, type Container } from 'pixi.js';

/**
 * Applies a ColorMatrixFilter to a container to simulate day/night cycle.
 *
 * At daytime=0.5 (noon): identity matrix — natural colors, full brightness.
 * At daytime=0.0 or 1.0 (midnight): dark and blue-shifted.
 * Values between are linearly interpolated for smooth transitions.
 */
export class DayNightFilter {
	private filter: ColorMatrixFilter;
	private containers: Container[];

	constructor(containers: Container | Container[]) {
		this.containers = Array.isArray(containers) ? containers : [containers];
		this.filter = new ColorMatrixFilter();
		for (const c of this.containers) {
			c.filters = [this.filter];
		}
	}

	/**
	 * Returns the current ColorMatrix coefficients as a Float32Array of length 20
	 * (5 columns x 4 rows in column-major order for PixiJS).
	 */
	getMatrix(): number[] {
		return this.filter.matrix as number[];
	}

	/**
	 * Updates the filter based on the daytime value.
	 * @param daytime — Value from 0.0 (midnight) → 0.5 (noon) → 1.0 (midnight)
	 */
	update(daytime: number): void {
		// Normalize: 0→0, 0.5→1, 1→0 (noon is peak brightness)
		const t = 1 - Math.abs(daytime - 0.5) * 2; // 0 at midnight, 1 at noon

		// Night matrix: dark + blue shift
		const night = [0.25, 0, 0, 0, 0, 0, 0.35, 0, 0, 0, 0, 0, 0.55, 0, 0, 0, 0, 0, 1, 0];

		// Day matrix: identity (natural colors)
		const day = [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0];

		// Lerp between night and day based on t
		const matrix = this.filter.matrix;
		for (let i = 0; i < matrix.length; i++) {
			matrix[i] = night[i] + (day[i] - night[i]) * t;
		}
	}

	/**
	 * Removes the filter from all containers and cleans up.
	 */
	destroy(): void {
		for (const c of this.containers) {
			c.filters = null;
		}
		this.filter.destroy();
	}
}
