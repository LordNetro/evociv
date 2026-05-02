<script lang="ts">
	import { T, useTask } from '@threlte/core';
	import { ShaderMaterial, Color, DoubleSide } from 'three';
	import pulseVert from '$lib/shaders/pulse.vert.glsl?raw';
	import pulseFrag from '$lib/shaders/pulse.frag.glsl?raw';
	import { uiStore } from '$lib/stores/uiStore.svelte.js';
	import { canvas3dStore } from './canvas3dStore.svelte.js';

	let selectedId = $derived($uiStore.selectedAgentId);
	let pos = $derived(selectedId ? canvas3dStore.agentPositions[selectedId] : undefined);

	const pulseMat = new ShaderMaterial({
		uniforms: {
			uTime: { value: 0 },
			uPulseSpeed: { value: 2.0 },
			uColor: { value: new Color(0xffd700) },
			uGlowColor: { value: new Color(0xffa500) }
		},
		vertexShader: pulseVert,
		fragmentShader: pulseFrag,
		transparent: true,
		side: DoubleSide,
		depthWrite: false
	});

	useTask((delta) => {
		pulseMat.uniforms.uTime.value += delta;
	});
</script>

{#if pos}
	<T.Mesh position={[pos.x + 0.5, 0.05, pos.y + 0.5]} rotation={[-Math.PI / 2, 0, 0]}>
		<T.RingGeometry args={[0.5, 0.6, 32]} />
		<T is={pulseMat} />
	</T.Mesh>
{/if}
