<script lang="ts">
	import { simulationStore } from '$lib/stores/simulationStore.svelte.js';

	interface ColonyStats {
		population: number;
		births: number;
		deaths: number;
		total_resources: Record<string, number>;
	}

	interface Faction {
		id: string;
		name: string;
		color: string;
		member_count: number;
		shared_resources: Record<string, number>;
	}

	let colony = $derived(($simulationStore.colony_stats ?? null) as ColonyStats | null);
	let factions = $derived(($simulationStore.factions ?? {}) as Record<string, Faction>);
	let showPanel = $state(false);

	function toggle() {
		showPanel = !showPanel;
	}
</script>

<button class="colony-toggle" onclick={toggle} aria-label="Toggle colony info">
	{showPanel ? 'Hide Colony' : 'Colony'}
</button>

{#if showPanel && colony}
	<div class="colony-panel">
		<h3 class="title">Colony Info</h3>

		<div class="section">
			<div class="kv-row">
				<span class="kv-key">Population</span>
				<span class="kv-value">{colony.population ?? 0}</span>
			</div>
			<div class="kv-row">
				<span class="kv-key">Births</span>
				<span class="kv-value">{colony.births ?? 0}</span>
			</div>
			<div class="kv-row">
				<span class="kv-key">Deaths</span>
				<span class="kv-value">{colony.deaths ?? 0}</span>
			</div>
		</div>

		{#if colony.total_resources && Object.keys(colony.total_resources).length > 0}
			<div class="section">
				<h4 class="section-title">Total Resources</h4>
				{#each Object.entries(colony.total_resources) as [res, qty] (res)}
					<div class="kv-row">
						<span class="kv-key">{res}</span>
						<span class="kv-value">{qty}</span>
					</div>
				{/each}
			</div>
		{/if}

		{#if factions && Object.keys(factions).length > 0}
			<div class="section">
				<h4 class="section-title">Factions</h4>
				{#each Object.values(factions) as f (f.id)}
					<div class="faction-card">
						<div class="faction-header">
							<span class="faction-dot" style="background-color: {f.color};"></span>
							<span class="faction-name">{f.name}</span>
							<span class="faction-count">({f.member_count})</span>
						</div>
						{#if f.shared_resources && Object.keys(f.shared_resources).length > 0}
							<div class="faction-resources">
								{#each Object.entries(f.shared_resources) as [res, qty] (res)}
									<span class="resource-tag">{res}: {qty}</span>
								{/each}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<style>
	.colony-toggle {
		position: fixed;
		right: 8px;
		bottom: 8px;
		z-index: 20;
		background: rgba(0, 0, 0, 0.75);
		color: #fff;
		border: 1px solid rgba(255, 255, 255, 0.25);
		padding: 6px 12px;
		border-radius: 6px;
		font-size: 13px;
		cursor: pointer;
		backdrop-filter: blur(4px);
	}

	.colony-panel {
		position: fixed;
		right: 8px;
		bottom: 44px;
		width: 240px;
		max-height: 60vh;
		overflow-y: auto;
		background: rgba(0, 0, 0, 0.85);
		color: #fff;
		padding: 14px;
		border-radius: 8px;
		font-family: system-ui, -apple-system, sans-serif;
		font-size: 13px;
		z-index: 20;
		backdrop-filter: blur(4px);
	}

	.title {
		margin: 0 0 10px;
		font-size: 14px;
		font-weight: 600;
	}

	.section {
		border-top: 1px solid rgba(255, 255, 255, 0.1);
		padding: 8px 0;
	}

	.section:first-of-type {
		border-top: none;
	}

	.section-title {
		margin: 0 0 6px;
		font-size: 12px;
		font-weight: 600;
		color: #aaa;
	}

	.kv-row {
		display: flex;
		justify-content: space-between;
		margin-bottom: 4px;
		font-size: 12px;
	}

	.kv-key {
		color: #aaa;
	}

	.kv-value {
		font-weight: 500;
	}

	.faction-card {
		background: rgba(255, 255, 255, 0.05);
		border-radius: 6px;
		padding: 6px 8px;
		margin-bottom: 6px;
	}

	.faction-header {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.faction-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		display: inline-block;
	}

	.faction-name {
		font-weight: 500;
	}

	.faction-count {
		color: #aaa;
		font-size: 11px;
	}

	.faction-resources {
		margin-top: 4px;
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
	}

	.resource-tag {
		font-size: 11px;
		background: rgba(255, 255, 255, 0.1);
		padding: 2px 6px;
		border-radius: 4px;
	}
</style>
