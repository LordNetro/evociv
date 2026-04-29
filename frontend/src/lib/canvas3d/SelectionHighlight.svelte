<script lang="ts">
	import { T, useTask } from '@threlte/core';
	import { uiStore } from '$lib/stores/uiStore.svelte.js';
	import { canvas3dStore } from './canvas3dStore.svelte.js';

	let rotation = $state(0);
	let scale = $state(1);

	let selectedId = $derived($uiStore.selectedAgentId);
	let pos = $derived(selectedId ? canvas3dStore.agentPositions[selectedId] : undefined);

	useTask((delta) => {
		rotation += delta * 2;
		scale = 1 + Math.sin(rotation * 3) * 0.1;
	});
</script>

{#if pos}
	<T.Mesh
		position={[pos.x + 0.5, 0.05, pos.y + 0.5]}
		rotation={[-Math.PI / 2, 0, rotation]}
		scale={[scale, scale, scale]}
	>
		<T.RingGeometry args={[0.5, 0.6, 32]} />
		<T.MeshStandardMaterial color="#FFD700" side={2} emissive="#FFD700" emissiveIntensity={0.5} />
	</T.Mesh>
{/if}
