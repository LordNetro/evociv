import type { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

/** Module-level reference to OrbitControls for WASD panning */
let controlsRef: OrbitControls | null = null;

export function setControls(c: OrbitControls) {
	// Disable right-click pan — we handle right-click manually for FPS-style camera
	c.mouseButtons = {
		LEFT: THREE_MOUSE.ROTATE,
		MIDDLE: THREE_MOUSE.DOLLY,
		RIGHT: null
	};
	// Also disable touch-based pan to avoid conflicts
	c.touches = {
		ONE: THREE_TOUCH.ROTATE,
		TWO: THREE_TOUCH.DOLLY_PAN
	};
	controlsRef = c;
}

export function getControls(): OrbitControls | null {
	return controlsRef;
}

// Three.js mouse/touch constants
const THREE_MOUSE = { LEFT: 0, MIDDLE: 1, RIGHT: 2, ROTATE: 0, DOLLY: 1, PAN: 2 };
const THREE_TOUCH = { ROTATE: 0, PAN: 1, DOLLY_PAN: 2, DOLLY_ROTATE: 3 };
