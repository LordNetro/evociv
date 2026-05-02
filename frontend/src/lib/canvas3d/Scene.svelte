<script lang="ts">
	import { Canvas } from '@threlte/core';
	import { WebGLRenderer, ACESFilmicToneMapping } from 'three';
	import InteractivityInit from './InteractivityInit.svelte';
	import AmbientParticles from './AmbientParticles.svelte';
	import PostProcessing from './PostProcessing.svelte';
	import SceneContent from './SceneContent.svelte';

	interface Props {
		children?: import('svelte').Snippet;
		bloomEnabled?: boolean;
	}

	let { children, bloomEnabled = true }: Props = $props();

	const createRenderer = (canvas: HTMLCanvasElement) => {
		const renderer = new WebGLRenderer({
			canvas,
			antialias: true,
			alpha: false
		});
		renderer.setClearColor(0x1a1a2e);
		renderer.toneMapping = ACESFilmicToneMapping;
		renderer.toneMappingExposure = 1.0;
		return renderer;
	};
</script>

<Canvas {createRenderer}>
	<InteractivityInit>
		<PostProcessing {bloomEnabled} />
		<SceneContent />
		<AmbientParticles />
		{@render children?.()}
	</InteractivityInit>
</Canvas>

<style>
	:global(canvas) {
		display: block;
		width: 100%;
		height: 100%;
	}
</style>
