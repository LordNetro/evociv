<script lang="ts">
	import { Canvas, T } from '@threlte/core';
	import { OrbitControls } from '@threlte/extras';
	import { WebGLRenderer } from 'three';
	import KeyboardPan from './KeyboardPan.svelte';
	import { setControls } from './controlsStore';

	interface Props {
		children?: import('svelte').Snippet;
	}

	let { children }: Props = $props();

	const createRenderer = (canvas: HTMLCanvasElement) => {
		const renderer = new WebGLRenderer({
			canvas,
			antialias: true,
			alpha: false
		});
		renderer.setClearColor(0x1a1a2e);
		return renderer;
	};
</script>

<Canvas {createRenderer}>
	<T.PerspectiveCamera
		makeDefault
		position={[35, 35, 35]}
		oncreate={(ref) => {
			ref.lookAt(0, 0, 0);
		}}
	>
		<OrbitControls
			enableDamping
			minDistance={5}
			maxDistance={100}
			oncreate={(c) => {
				setControls(c);
			}}
		/>
	</T.PerspectiveCamera>

	<T.AmbientLight intensity={0.5} />
	<T.DirectionalLight position={[10, 20, 10]} intensity={1.0} />

	<KeyboardPan />
	{@render children?.()}
</Canvas>

<style>
	:global(canvas) {
		display: block;
		width: 100%;
		height: 100%;
	}
</style>
