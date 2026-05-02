<script lang="ts">
	import { interactivity } from '@threlte/extras';
	import { useThrelte } from '@threlte/core';
	import { FogExp2 } from 'three';

	/**
	 * Initializes Threlte 8's interactivity (pointer events, click handling).
	 * MUST be called INSIDE the <Canvas> context because it uses useDOM().
	 * This wrapper component sets the interactivity context + plugin so that
	 * child <T.Mesh on:click> components can receive pointer events.
	 */
	interactivity();

	const { scene } = useThrelte();
	scene.fog = new FogExp2(0x1a1a2e, 0.008);

	interface Props {
		children?: import('svelte').Snippet;
	}

	let { children }: Props = $props();
</script>

{@render children?.()}
