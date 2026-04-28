export function lerp(a: number, b: number, t: number): number {
	return a + (b - a) * t;
}

export function easeInOut(t: number): number {
	return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
}

export function clamp(value: number, min: number, max: number): number {
	return Math.min(Math.max(value, min), max);
}

export function mapRange(
	value: number,
	inMin: number,
	inMax: number,
	outMin: number,
	outMax: number
): number {
	return outMin + (outMax - outMin) * ((value - inMin) / (inMax - inMin));
}
