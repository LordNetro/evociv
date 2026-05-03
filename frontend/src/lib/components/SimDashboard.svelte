<script lang="ts">
	import { simulationStore } from '$lib/stores/simulationStore.svelte.js';
	import { uiStore } from '$lib/stores/uiStore.svelte.js';

	let showPanel = $state(false);

	// ----- Agent action distribution -----
	let actionDistribution = $derived.by(() => {
		const agents = ($simulationStore.agents ?? {}) as Record<string, { current_action?: string | null; role?: string }>;
		const actions: Record<string, number> = {};
		const roles: Record<string, number> = {};
		for (const a of Object.values(agents)) {
			const action = a.current_action ?? 'idle';
			actions[action] = (actions[action] ?? 0) + 1;
			const role = a.role ?? 'unknown';
			roles[role] = (roles[role] ?? 0) + 1;
		}
		return { actions, roles, total: Object.keys(agents).length };
	});

	// ----- Events by type -----
	let eventCounts = $derived.by(() => {
		const events = ($simulationStore.events ?? []) as Array<{ type: string }>;
		const counts: Record<string, number> = {};
		for (const e of events) {
			counts[e.type] = (counts[e.type] ?? 0) + 1;
		}
		return counts;
	});

	// ----- Colony stats -----
	let colony = $derived(($simulationStore.colony_stats ?? null) as {
		population?: number; births?: number; deaths?: number; total_resources?: Record<string, number>;
	} | null);
	let metrics = $derived(($simulationStore.metrics ?? {}) as {
		avg_hunger?: number; avg_thirst?: number; avg_health?: number; avg_energy?: number;
	});
	let factions = $derived(($simulationStore.factions ?? {}) as Record<string, {
		id: string; name: string; color: string; member_count: number;
	}>);

	// ----- Structures -----
	let structures = $derived(
		(Object.values(($simulationStore as Record<string, unknown>).structures ?? {}) as Array<{
			id: string; structure_type: string; owner_id?: string | null; health?: number;
		}>)
	);

	// ----- Time / Weather -----
	let timeState = $derived(
		($simulationStore as Record<string, unknown>).time_state as {
			is_night?: boolean; day_count?: number; time_of_day_label?: string; tick_count_of_day?: number;
		} | undefined
	);
	let weatherState = $derived(
		($simulationStore as Record<string, unknown>).weather_state as {
			temperature?: number; precipitation?: string;
		} | undefined
	);

	// ----- Latest events (last 10) -----
	let latestEvents = $derived(
		(($simulationStore.events ?? []) as Array<{ type: string; description: string; tick: number }>).slice(-10).reverse()
	);

	// Count structures by type
	let structureCounts = $derived.by(() => {
		const counts: Record<string, number> = {};
		for (const s of structures) {
			counts[s.structure_type] = (counts[s.structure_type] ?? 0) + 1;
		}
		return counts;
	});

	function toggle() { showPanel = !showPanel; }

	const ACTION_EMOJIS: Record<string, string> = {
		move: '🚶', idle: '💤', rest: '😴', eat: '🍽️', drink: '💧',
		gather: '🌿', chop: '🪓', mine: '⛏️', hunt: '🏹', fish: '🎣',
		farm: '🌱', craft: '🔧', build: '🏗️', socialize: '🗣️', trade: '🤝',
		reproduce: '👶', feed_child: '🍼', explore: '🔍', attack: '⚔️', guard: '🛡️', heal: '💊'
	};
</script>

<button class="dash-toggle" onclick={toggle} aria-label="Toggle simulation status">
	📊
</button>

{#if showPanel}
	<div class="dash-panel">
		<h3 class="title">Simulation Status</h3>

		<!-- Tick + Time -->
		<div class="stat-row">
			<span class="label">Tick</span>
			<span class="value">{($simulationStore as Record<string, unknown>).tick as number ?? 0}</span>
		</div>
		{#if timeState}
			<div class="stat-row">
				<span class="label">Day</span>
				<span class="value">{timeState.day_count ?? 0} {timeState.time_of_day_label ?? ''} {timeState.is_night ? '🌙' : '☀️'}</span>
			</div>
		{/if}
		{#if weatherState}
			<div class="stat-row">
				<span class="label">Weather</span>
				<span class="value">{weatherState.precipitation ?? 'clear'} {weatherState.temperature != null ? `${weatherState.temperature}°C` : ''}</span>
			</div>
		{/if}

		<!-- Population -->
		<div class="section-title">Population</div>
		<div class="stat-row">
			<span class="label">Total</span>
			<span class="value">{colony?.population ?? actionDistribution.total}</span>
		</div>
		<div class="stat-row">
			<span class="label">Born / Died</span>
			<span class="value">{colony?.births ?? 0} / {colony?.deaths ?? 0}</span>
		</div>

		<!-- Agent stats -->
		<div class="section-title">Agent Health</div>
		<div class="stat-row">
			<span class="label">Avg Hunger</span>
			<span class="value">{Math.round(metrics.avg_hunger ?? 0)}%</span>
		</div>
		<div class="stat-row">
			<span class="label">Avg Thirst</span>
			<span class="value">{Math.round(metrics.avg_thirst ?? 0)}%</span>
		</div>
		<div class="stat-row">
			<span class="label">Avg Health</span>
			<span class="value">{Math.round(metrics.avg_health ?? 0)}%</span>
		</div>

		<!-- Current Actions -->
		{#if Object.keys(actionDistribution.actions).length > 0}
			<div class="section-title">Agent Actions</div>
			{#each Object.entries(actionDistribution.actions).sort((a, b) => b[1] - a[1]) as [action, count]}
				<div class="stat-row">
					<span class="label">{ACTION_EMOJIS[action] ?? '❓'} {action}</span>
					<span class="value">{count}</span>
				</div>
			{/each}
		{/if}

		<!-- Roles -->
		{#if Object.keys(actionDistribution.roles).length > 0}
			<div class="section-title">Roles</div>
			{#each Object.entries(actionDistribution.roles).sort((a, b) => b[1] - a[1]) as [role, count]}
				<div class="stat-row">
					<span class="label">{role}</span>
					<span class="value">{count}</span>
				</div>
			{/each}
		{/if}

		<!-- Structures -->
		{#if Object.keys(structureCounts).length > 0}
			<div class="section-title">Structures ({structures.length})</div>
			{#each Object.entries(structureCounts).sort((a, b) => b[1] - a[1]) as [type, count]}
				<div class="stat-row">
					<span class="label">🏛️ {type}</span>
					<span class="value">{count}</span>
				</div>
			{/each}
		{/if}

		<!-- Events by type -->
		{#if Object.keys(eventCounts).length > 0}
			<div class="section-title">Events</div>
			{#each Object.entries(eventCounts).sort((a, b) => b[1] - a[1]) as [type, count]}
				<div class="stat-row">
					<span class="label">{type}</span>
					<span class="value">{count}</span>
				</div>
			{/each}
		{/if}

		<!-- Factions -->
		{#if Object.keys(factions).length > 0}
			<div class="section-title">Factions</div>
			{#each Object.values(factions) as f (f.id)}
				<div class="faction-row">
					<span class="faction-dot" style="background: {f.color};"></span>
					<span>{f.name}</span>
					<span class="faction-pop">({f.member_count})</span>
				</div>
			{/each}
		{/if}

		<!-- Colony Resources -->
		{#if colony?.total_resources && Object.keys(colony.total_resources).length > 0}
			<div class="section-title">Resources</div>
			{#each Object.entries(colony.total_resources).sort((a, b) => b[1] - a[1]) as [res, qty]}
				<div class="stat-row">
					<span class="label">{res}</span>
					<span class="value">{qty}</span>
				</div>
			{/each}
		{/if}

		<!-- Latest events -->
		{#if latestEvents.length > 0}
			<div class="section-title">Latest Events</div>
			<div class="event-list">
				{#each latestEvents as ev (ev.tick + ev.description)}
					<div class="event-line">{ev.description}</div>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<style>
	.dash-toggle {
		position: fixed;
		left: 8px;
		bottom: 8px;
		z-index: 30;
		background: rgba(0, 0, 0, 0.75);
		color: #fff;
		border: 1px solid rgba(255, 255, 255, 0.25);
		padding: 6px 12px;
		border-radius: 6px;
		font-size: 16px;
		cursor: pointer;
		backdrop-filter: blur(4px);
	}
	.dash-panel {
		position: fixed;
		left: 8px;
		bottom: 44px;
		width: 280px;
		max-height: 70vh;
		overflow-y: auto;
		background: rgba(0, 0, 0, 0.88);
		color: #fff;
		padding: 12px;
		border-radius: 8px;
		font-family: system-ui, -apple-system, sans-serif;
		font-size: 12px;
		z-index: 30;
		backdrop-filter: blur(4px);
	}
	.title {
		margin: 0 0 8px;
		font-size: 14px;
		font-weight: 600;
	}
	.section-title {
		font-size: 11px;
		font-weight: 600;
		color: #888;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		margin-top: 10px;
		margin-bottom: 4px;
		border-top: 1px solid rgba(255,255,255,0.08);
		padding-top: 6px;
	}
	.stat-row {
		display: flex;
		justify-content: space-between;
		padding: 1px 0;
	}
	.label { color: #ccc; }
	.value { font-weight: 500; color: #fff; }
	.faction-row {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 2px 0;
	}
	.faction-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		display: inline-block;
		flex-shrink: 0;
	}
	.faction-pop { color: #888; margin-left: auto; }
	.event-list {
		max-height: 120px;
		overflow-y: auto;
		margin-top: 4px;
	}
	.event-line {
		font-size: 11px;
		color: #aaa;
		padding: 1px 0;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
</style>
