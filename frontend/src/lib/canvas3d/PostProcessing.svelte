<script lang="ts">
	import { useThrelte, useTask } from '@threlte/core';
	import { Vector2 } from 'three';
	import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
	import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
	import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
	import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';

	/**
	 * Post-processing pipeline with bloom.
	 * MUST be inside <Canvas> context — uses useThrelte().
	 */
	interface Props {
		bloomEnabled?: boolean;
	}

	let { bloomEnabled = true }: Props = $props();

	const { renderer, scene, camera, renderStage, autoRenderTask } = useThrelte();

	let composer: EffectComposer | null = null;

	$effect(() => {
		if (!renderer) return;

		composer = new EffectComposer(renderer);
		composer.addPass(new RenderPass(scene, camera.current));

		const bloomPass = new UnrealBloomPass(
			new Vector2(window.innerWidth, window.innerHeight),
			bloomEnabled ? 0.3 : 0,
			0.5,
			0.8
		);
		composer.addPass(bloomPass);
		composer.addPass(new OutputPass());

		const canvasEl = renderer.domElement;
		const observer = new ResizeObserver((entries) => {
			for (const entry of entries) {
				const { width, height } = entry.contentRect;
				composer?.setSize(width, height);
			}
		});
		observer.observe(canvasEl.parentElement ?? canvasEl);

		return () => {
			observer.disconnect();
			composer?.dispose();
			composer = null;
		};
	});

	$effect(() => {
		if (composer) {
			const bloomPass = composer.passes.find((p) => p instanceof UnrealBloomPass) as
				| UnrealBloomPass
				| undefined;
			if (bloomPass) {
				bloomPass.strength = bloomEnabled ? 0.3 : 0;
			}
		}
	});

	useTask(
		() => {
			if (composer) {
				composer.render();
			}
		},
		{ stage: renderStage, after: autoRenderTask }
	);
</script>
