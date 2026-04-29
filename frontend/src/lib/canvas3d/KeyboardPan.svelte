<script lang="ts">
	import { useTask, useThrelte } from '@threlte/core';
	import { Vector3, Spherical } from 'three';
	import { onMount } from 'svelte';
	import { getControls } from './controlsStore';

	const WALK_SPEED = 15;
	const MOUSE_SENSITIVITY = 0.003;

	// eslint-disable-next-line svelte/prefer-svelte-reactivity
	const pressed = new Set<string>();
	let isRightDown = false;
	const ctx = useThrelte();

	function getCanvas(): HTMLCanvasElement | null {
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		const r = (ctx as any).renderer;
		return r?.domElement ?? null;
	}

	function onKeyDown(e: KeyboardEvent) {
		pressed.add(e.code);
	}
	function onKeyUp(e: KeyboardEvent) {
		pressed.delete(e.code);
	}

	function onPointerLockChange() {
		if (!document.pointerLockElement) {
			isRightDown = false;
		}
	}

	onMount(() => {
		window.addEventListener('keydown', onKeyDown);
		window.addEventListener('keyup', onKeyUp);

		const canvas = getCanvas();
		if (canvas) {
			canvas.addEventListener('contextmenu', (e: MouseEvent) => e.preventDefault());

			// Right-click → request pointer lock (mouse disappears, stays in canvas)
			canvas.addEventListener(
				'mousedown',
				(e: MouseEvent) => {
					if (e.button === 2) {
						isRightDown = true;
						canvas.requestPointerLock();
						e.stopPropagation();
					}
				},
				true
			);

			// Release right-click → exit pointer lock
			canvas.addEventListener(
				'mouseup',
				(e: MouseEvent) => {
					if (e.button === 2 && document.pointerLockElement) {
						document.exitPointerLock();
					}
				},
				true
			);

			// Track pointer lock state (Escape also exits pointer lock)
			document.addEventListener('pointerlockchange', onPointerLockChange);

			// Mouse move — only processes when pointer is locked (right-click held)
			canvas.addEventListener(
				'mousemove',
				(e: MouseEvent) => {
					if (!isRightDown) return;
					const controls = getControls();
					if (!controls) return;
					const offset = new Vector3().copy(controls.object.position).sub(controls.target);
					const spherical = new Spherical().setFromVector3(offset);
					spherical.theta -= e.movementX * MOUSE_SENSITIVITY;
					spherical.phi -= e.movementY * MOUSE_SENSITIVITY;
					spherical.phi = Math.max(0.01, Math.min(Math.PI - 0.01, spherical.phi));
					offset.setFromSpherical(spherical);
					controls.target.copy(controls.object.position).sub(offset);
				},
				true
			);
		}
		return () => {
			window.removeEventListener('keydown', onKeyDown);
			window.removeEventListener('keyup', onKeyUp);
			document.removeEventListener('pointerlockchange', onPointerLockChange);
		};
	});

	useTask((delta) => {
		const controls = getControls();
		if (!controls) return;
		if (!isRightDown && pressed.size === 0) return;

		const forward = new Vector3();
		controls.object.getWorldDirection(forward);

		if (isRightDown) {
			const right = new Vector3();
			right.crossVectors(forward, new Vector3(0, 1, 0)).normalize();
			const movement = new Vector3(0, 0, 0);
			if (pressed.has('KeyW') || pressed.has('ArrowUp')) movement.add(forward);
			if (pressed.has('KeyS') || pressed.has('ArrowDown')) movement.sub(forward);
			if (pressed.has('KeyA') || pressed.has('ArrowLeft')) movement.sub(right);
			if (pressed.has('KeyD') || pressed.has('ArrowRight')) movement.add(right);
			if (pressed.has('Space')) movement.y += 1;
			if (pressed.has('ShiftLeft') || pressed.has('ShiftRight')) movement.y -= 1;
			if (movement.lengthSq() > 0) {
				movement.normalize().multiplyScalar(WALK_SPEED * delta);
				controls.target.add(movement);
				controls.object.position.add(movement);
			}
		} else {
			const flatForward = new Vector3(forward.x, 0, forward.z);
			if (flatForward.lengthSq() < 0.001) return;
			flatForward.normalize();
			const right = new Vector3(-flatForward.z, 0, flatForward.x);
			const movement = new Vector3(0, 0, 0);
			if (pressed.has('KeyW') || pressed.has('ArrowUp')) movement.add(flatForward);
			if (pressed.has('KeyS') || pressed.has('ArrowDown')) movement.sub(flatForward);
			if (pressed.has('KeyA') || pressed.has('ArrowLeft')) movement.sub(right);
			if (pressed.has('KeyD') || pressed.has('ArrowRight')) movement.add(right);
			if (movement.lengthSq() > 0) {
				const dist = controls.object.position.distanceTo(controls.target);
				const speed = WALK_SPEED * Math.max(1, dist / 10);
				movement.normalize().multiplyScalar(speed * delta);
				controls.target.add(movement);
			}
		}
	});
</script>
