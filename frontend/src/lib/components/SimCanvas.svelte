<script lang="ts">
	import Scene from '$lib/canvas3d/Scene.svelte';
	import Grid3D from '$lib/canvas3d/Grid3D.svelte';
	import Resources3D from '$lib/canvas3d/Resources3D.svelte';
	import WaterPlane from '$lib/canvas3d/WaterPlane.svelte';
	import Agents3D from '$lib/canvas3d/Agents3D.svelte';
	import AgentLabel from '$lib/canvas3d/AgentLabel.svelte';
	import SelectionHighlight from '$lib/canvas3d/SelectionHighlight.svelte';
	import HarvestEffect from '$lib/canvas3d/HarvestEffect.svelte';
	import { simulationStore } from '$lib/stores/simulationStore.svelte.js';

	interface TileData {
		x: number;
		y: number;
		resource_type: string | null;
		amount: number;
	}

	interface AgentState {
		id?: string;
		name?: string;
		current_action_emoji?: string;
		position?: [number, number];
		role?: string;
		faction_id?: string;
		is_child?: boolean;
	}

	interface FactionState {
		color: string;
	}

	interface Snapshot {
		tiles?: TileData[];
		agents?: Record<string, AgentState>;
		factions?: Record<string, FactionState>;
	}

	let snapshot = $derived(($simulationStore as Snapshot) ?? {});
	let tiles = $derived(snapshot.tiles ?? []);
	let waterTiles = $derived(tiles.filter((t) => t.resource_type === 'water'));
	let resourceTiles = $derived(
		tiles.filter((t) => t.resource_type !== null && t.resource_type !== 'water')
	);
	let agents = $derived(snapshot.agents ?? {});
	let factions = $derived(snapshot.factions ?? {});

	let harvestBursts = $state<{ id: number; x: number; y: number; type: string }[]>([]);
	let nextBurstId = 0;

	function handleHarvest(x: number, y: number, type: string) {
		harvestBursts = [...harvestBursts, { x, y, type, id: nextBurstId++ }];
	}

	function removeBurst(id: number) {
		harvestBursts = harvestBursts.filter((b) => b.id !== id);
	}
</script>

<div class="scene-wrapper">
	<Scene>
		<Grid3D {tiles} />
		<WaterPlane {waterTiles} />
		<Resources3D resources={resourceTiles} onHarvest={handleHarvest} />
		<Agents3D {agents} {factions} />
		{#each Object.entries(agents) as [id, agent] (id)}
			<AgentLabel agent={{ ...agent, id }} />
		{/each}
		<SelectionHighlight />
		<HarvestEffect bursts={harvestBursts} onComplete={removeBurst} />
	</Scene>
</div>

<style>
	.scene-wrapper {
		width: 100%;
		height: 100%;
		display: block;
	}
</style>
