<script lang="ts">
	import { T, useTask } from '@threlte/core';
	import { ShaderMaterial } from 'three';
	import * as THREE from 'three';
	import gridVert from '$lib/shaders/grid.vert.glsl?raw';
	import gridFrag from '$lib/shaders/grid.frag.glsl?raw';

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
		iron_ore: new THREE.Color('#5c6bc0'),
		clay: new THREE.Color('#bcaaa4'),
		sand: new THREE.Color('#fff59d'),
		fiber: new THREE.Color('#81c784'),
		deer: new THREE.Color('#8d6e63'),
		rabbit: new THREE.Color('#a1887f'),
		boar: new THREE.Color('#6d4c41'),
		default: new THREE.Color('#3e2723')
	};

	let meshRef: THREE.InstancedMesh | undefined = $state();

	const gridMat = new ShaderMaterial({
		uniforms: {
			uTime: { value: 0 },
			uHeightScale: { value: 0.02 },
			uLineWidth: { value: 0.02 },
			uLineSpacing: { value: 1.0 }
		},
		vertexShader: gridVert,
		fragmentShader: gridFrag
	});

	useTask((delta) => {
		gridMat.uniforms.uTime.value += delta;
	});

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
	<T.BoxGeometry args={[0.98, 0.08, 0.98]} />
	<T is={gridMat} />
</T.InstancedMesh>
