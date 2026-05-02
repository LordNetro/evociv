<script lang="ts">
	import { T, useTask } from '@threlte/core';
	import { ShaderMaterial, Color, DoubleSide } from 'three';
	import waterVert from '$lib/shaders/water.vert.glsl?raw';
	import waterFrag from '$lib/shaders/water.frag.glsl?raw';

	interface TileData {
		x: number;
		y: number;
		resource_type: string | null;
		amount: number;
	}

	interface Props {
		waterTiles: TileData[];
	}

	let { waterTiles }: Props = $props();

	function getBoundingBox(tiles: TileData[]) {
		if (tiles.length === 0) return null;
		let minX = Infinity;
		let minY = Infinity;
		let maxX = -Infinity;
		let maxY = -Infinity;
		for (const t of tiles) {
			minX = Math.min(minX, t.x);
			minY = Math.min(minY, t.y);
			maxX = Math.max(maxX, t.x);
			maxY = Math.max(maxY, t.y);
		}
		// Tile centers are at x+0.5, y+0.5 in world space
		return {
			centerX: (minX + maxX) / 2 + 0.5,
			centerY: (minY + maxY) / 2 + 0.5,
			width: maxX - minX + 1,
			depth: maxY - minY + 1
		};
	}

	let bbox = $derived(getBoundingBox(waterTiles));

	const waterMat = new ShaderMaterial({
		uniforms: {
			uTime: { value: 0 },
			uWaveSpeed: { value: 0.5 },
			uWaveAmp: { value: 0.15 },
			uColor: { value: new Color(0x42a5f5) },
			uDeepColor: { value: new Color(0x0d47a1) }
		},
		vertexShader: waterVert,
		fragmentShader: waterFrag,
		transparent: true,
		side: DoubleSide
	});

	useTask((delta) => {
		waterMat.uniforms.uTime.value += delta;
	});
</script>

{#if bbox}
	<!-- Water plane at y=0.051 (just above grid tile surface at y=0.05) -->
	<T.Mesh position={[bbox.centerX, 0.051, bbox.centerY]} rotation={[-Math.PI / 2, 0, 0]}>
		<T.PlaneGeometry args={[bbox.width, bbox.depth]} />
		<T is={waterMat} />
	</T.Mesh>
{/if}
