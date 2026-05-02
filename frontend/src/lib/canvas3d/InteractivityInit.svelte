<script lang="ts">
	import { interactivity } from '@threlte/extras';

	/**
	 * Initializes Threlte 8's interactivity (pointer events, click handling).
	 * MUST be called INSIDE the <Canvas> context because it uses useDOM().
	 * This wrapper component sets the interactivity context + plugin so that
	 * child <T.Mesh on:click> components can receive pointer events.
	 */
	interactivity();

	interface Props {
		children?: import('svelte').Snippet;
	}

	let { children }: Props = $props();
</script>

{@render children?.()}
