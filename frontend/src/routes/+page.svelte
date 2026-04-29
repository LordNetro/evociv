<script lang="ts">
	import { onMount } from 'svelte';
	import SimCanvas from '$lib/components/SimCanvas.svelte';
	import HUD from '$lib/components/HUD.svelte';
	import MetricChart from '$lib/components/MetricChart.svelte';
	import AgentInspector from '$lib/components/AgentInspector.svelte';
	import EventLog from '$lib/components/EventLog.svelte';
	import ColonyInfo from '$lib/components/ColonyInfo.svelte';
	import { connect, disconnect } from '$lib/components/ws.js';

	onMount(() => {
		connect();
		return () => disconnect();
	});
</script>

<div class="app">
	<SimCanvas config={{ tileSize: 32, gridWidth: 50, gridHeight: 50 }} />
	<HUD />
	<MetricChart />
	<AgentInspector />
	<EventLog />
	<ColonyInfo />
</div>

<style>
	:global(body) {
		margin: 0;
		padding: 0;
		overflow: hidden;
		background: #1a1a2e;
		color: #fff;
		font-family:
			system-ui,
			-apple-system,
			sans-serif;
	}

	.app {
		width: 100vw;
		height: 100vh;
		position: relative;
	}

	:global(.hud),
	:global(.inspector),
	:global(.event-log) {
		font-family:
			system-ui,
			-apple-system,
			sans-serif;
	}
</style>
