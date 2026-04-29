<script lang="ts">
	import { simulationStore } from '$lib/stores/simulationStore.svelte.js';

	interface ColonyStats {
		population: number;
		births: number;
		deaths: number;
		total_resources: Record<string, number>;
	}

	let colony = $derived(($simulationStore.colony_stats ?? null) as ColonyStats | null);
	let factions = $derived(($simulationStore.factions ?? {}) as Record<string, unknown>);
	let factionCount = $derived(Object.keys(factions).length);
</script>

<div class="hud-widgets">
	<div class="widget" title="Population">
		<span class="widget-icon">👥</span>
		<span class="widget-value">{colony?.population ?? 0}</span>
	</div>
	<div class="widget" title="Births this session">
		<span class="widget-icon">👶</span>
		<span class="widget-value">{colony?.births ?? 0}</span>
	</div>
	<div class="widget" title="Deaths this session">
		<span class="widget-icon">💀</span>
		<span class="widget-value">{colony?.deaths ?? 0}</span>
	</div>
	<div class="widget" title="Active factions">
		<span class="widget-icon">🚩</span>
		<span class="widget-value">{factionCount}</span>
	</div>
</div>

<style>
	.hud-widgets {
		display: flex;
		gap: 10px;
		align-items: center;
	}

	.widget {
		display: flex;
		align-items: center;
		gap: 4px;
		background: rgba(255, 255, 255, 0.08);
		padding: 4px 10px;
		border-radius: 6px;
		font-size: 13px;
	}

	.widget-icon {
		font-size: 14px;
	}

	.widget-value {
		font-weight: 600;
		color: #fff;
	}
</style>
