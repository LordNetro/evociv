<script lang="ts">
	import { T } from '@threlte/core';

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
</script>

{#if bbox}
	<!-- Water plane at y=0.051 (just above grid tile surface at y=0.05) -->
	<T.Mesh position={[bbox.centerX, 0.051, bbox.centerY]} rotation={[-Math.PI / 2, 0, 0]}>
		<T.PlaneGeometry args={[bbox.width, bbox.depth]} />
		<T.MeshStandardMaterial color="#1565c0" transparent opacity={0.5} />
	</T.Mesh>
{/if}
