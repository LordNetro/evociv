<script lang="ts">
	import { T } from '@threlte/core';

	interface TileData {
		x: number;
		y: number;
		resource_type: string | null;
		amount: number;
	}

	interface Props {
		resources: TileData[];
	}

	let { resources }: Props = $props();

	const RESOURCE_TYPES = ['tree', 'berries', 'stone'];

	function isRenderable(tile: TileData): boolean {
		return tile.resource_type !== null && RESOURCE_TYPES.includes(tile.resource_type);
	}
</script>

{#each resources.filter(isRenderable) as tile (tile.x + ',' + tile.y)}
	{#if tile.resource_type === 'tree'}
		<T.Group position={[tile.x + 0.5, 0.1, tile.y + 0.5]}>
			<T.Mesh position={[0, 0.15, 0]}>
				<T.CylinderGeometry args={[0.08, 0.1, 0.3]} />
				<T.MeshStandardMaterial color="#5d4037" />
			</T.Mesh>
			<T.Mesh position={[0, 0.5, 0]}>
				<T.ConeGeometry args={[0.4, 0.8]} />
				<T.MeshStandardMaterial color="#2e7d32" />
			</T.Mesh>
		</T.Group>
	{:else if tile.resource_type === 'berries'}
		<T.Mesh position={[tile.x + 0.5, 0.2, tile.y + 0.5]}>
			<T.SphereGeometry args={[0.2]} />
			<T.MeshStandardMaterial color="#e53935" />
		</T.Mesh>
	{:else if tile.resource_type === 'stone'}
		<T.Mesh position={[tile.x + 0.5, 0.2, tile.y + 0.5]}>
			<T.BoxGeometry args={[0.35, 0.25, 0.35]} />
			<T.MeshStandardMaterial color="#9E9E9E" />
		</T.Mesh>
	{/if}
{/each}
