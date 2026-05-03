import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockContainerFilters: any[] = [];

vi.mock('pixi.js', () => ({
	Container: vi.fn().mockImplementation(() => ({
		filters: mockContainerFilters
	})),
	ColorMatrixFilter: vi.fn().mockImplementation(() => ({
		matrix: new Float32Array([1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0]),
		destroy: vi.fn()
	}))
}));

import { DayNightFilter } from '../DayNightFilter';
import { Container, ColorMatrixFilter } from 'pixi.js';

/**
 * Identity matrix for ColorMatrixFilter (5 columns x 4 rows):
 * [1, 0, 0, 0, 0]
 * [0, 1, 0, 0, 0]
 * [0, 0, 1, 0, 0]
 * [0, 0, 0, 1, 0]
 */
const IDENTITY_MATRIX = new Float32Array([
	1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0
]);

describe('DayNightFilter', () => {
	let container: Container;
	let filter: DayNightFilter;

	beforeEach(() => {
		vi.clearAllMocks();
		mockContainerFilters.length = 0;
		container = new Container();
		filter = new DayNightFilter(container);
	});

	it('should apply a ColorMatrixFilter to the container', () => {
		expect(container.filters).toBeDefined();
		expect(container.filters!.length).toBe(1);
		// Verify it has the matrix property that ColorMatrixFilter provides
		expect((container.filters![0] as any).matrix).toBeDefined();
		expect((container.filters![0] as any).matrix instanceof Float32Array).toBe(true);
	});

	it('should set identity matrix at daytime 0.5 (noon)', () => {
		filter.update(0.5);
		const matrix = filter.getMatrix();
		for (let i = 0; i < IDENTITY_MATRIX.length; i++) {
			expect(matrix[i]).toBeCloseTo(IDENTITY_MATRIX[i], 5);
		}
	});

	it('should darken and blue-shift at daytime 0 (midnight)', () => {
		filter.update(0);
		const matrix = filter.getMatrix();

		// Red channel multiplier should be reduced (darker)
		expect(matrix[0]).toBeLessThan(0.5);
		// Green channel multiplier should be reduced (darker)
		expect(matrix[6]).toBeLessThan(0.5);
		// Blue channel multiplier should be higher than red (blue shift)
		expect(matrix[12]).toBeGreaterThan(matrix[0]);
		expect(matrix[12]).toBeGreaterThan(matrix[6]);
	});

	it('should produce the same matrix at daytime 0 and 1.0 (cyclic)', () => {
		filter.update(0);
		const midnightMatrix = filter.getMatrix().slice();

		filter.update(1.0);
		const fullCycleMatrix = filter.getMatrix();

		expect(fullCycleMatrix).toEqual(midnightMatrix);
	});

	it('should produce correct values at daytime 0.25 (dawn/dusk transition)', () => {
		filter.update(0.25);
		const matrix = filter.getMatrix();

		const midnightFilter = new DayNightFilter(new Container());
		midnightFilter.update(0);
		const midnightMatrix = midnightFilter.getMatrix();

		const noonFilter = new DayNightFilter(new Container());
		noonFilter.update(0.5);
		const noonMatrix = noonFilter.getMatrix();

		// matrix should be between midnight and noon
		for (let i = 0; i < matrix.length; i++) {
			const min = Math.min(midnightMatrix[i], noonMatrix[i]);
			const max = Math.max(midnightMatrix[i], noonMatrix[i]);
			expect(matrix[i]).toBeGreaterThanOrEqual(min - 0.01);
			expect(matrix[i]).toBeLessThanOrEqual(max + 0.01);
		}
	});

	it('should update the matrix on the filter', () => {
		filter.update(0.5);
		const noonMatrix = filter.getMatrix().slice();

		filter.update(0);
		const midnightMatrix = filter.getMatrix();

		// Should differ from noon
		const differs = midnightMatrix.some((v, i) => Math.abs(v - noonMatrix[i]) > 0.01);
		expect(differs).toBe(true);
	});

	it('should have a destroy method that removes filters from the container', () => {
		filter.destroy();
		expect(container.filters).toBeNull();
	});
});
