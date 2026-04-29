<script lang="ts">
	import { T } from '@threlte/core';

	import * as THREE from 'three';

	interface TileData {
		x: number;
		y: number;
		resource_type: string | null;
		amount: number;
	}

	interface Props {
		tiles: TileData[];
	}

	let { tiles }: Props = $props();

	const COLOR_MAP: Record<string, THREE.Color> = {
		water: new THREE.Color('#1565c0'),
		tree: new THREE.Color('#2e7d32'),
		berries: new THREE.Color('#c62828'),
		stone: new THREE.Color('#757575'),
		default: new THREE.Color('#5d4037')
	};

	let meshRef: THREE.InstancedMesh | undefined = $state();

	function updateInstances(currentTiles: TileData[]) {
		if (!meshRef) return;
		meshRef.count = currentTiles.length;

		const dummy = new THREE.Object3D();
		for (let i = 0; i < currentTiles.length; i++) {
			const tile = currentTiles[i];
			dummy.position.set(tile.x, 0, tile.y);
			dummy.updateMatrix();
			meshRef.setMatrixAt(i, dummy.matrix);

			const color = COLOR_MAP[tile.resource_type ?? ''] ?? COLOR_MAP.default;
			meshRef.setColorAt(i, color);
		}

		meshRef.instanceMatrix.needsUpdate = true;
		if (meshRef.instanceColor) meshRef.instanceColor.needsUpdate = true;
	}

	$effect(() => {
		updateInstances(tiles);
		// Disable frustum culling on InstancedMesh so tiles don't pop in/out
		if (meshRef) {
			meshRef.frustumCulled = false;
		}
	});
</script>

<T.InstancedMesh bind:ref={meshRef}>
	<T.BoxGeometry args={[1, 0.1, 1]} />
	<T.MeshStandardMaterial />
</T.InstancedMesh>
