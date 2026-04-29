<script lang="ts">
	import { simulationStore } from '$lib/stores/simulationStore.svelte.js';
	import { uiStore } from '$lib/stores/uiStore.svelte.js';

	interface AgentData {
		id?: string;
		name?: string;
		role?: string;
		sex?: string;
		age?: number;
		max_age?: number;
		hunger?: number;
		thirst?: number;
		energy?: number;
		health?: number;
		strength?: number;
		intelligence?: number;
		sociability?: number;
		speed?: number;
		current_state?: string;
		current_action?: string;
		current_action_emoji?: string;
		action_progress?: number;
		inventory?: Record<string, number>;
		last_thought?: string;
		system_prompt?: string;
		monologue_history?: string[];
		relationships?: Record<
			string,
			{ interaction_count: number; last_interaction_tick: number; score: number }
		>;
		faction_id?: string;
		knowledge?: Record<string, Record<string, unknown>>;
		is_child?: boolean;
		parent_id?: string;
		maturity_age?: number;
		[key: string]: unknown;
	}

	interface FactionData {
		id: string;
		name: string;
		color: string;
		member_count: number;
		shared_resources: Record<string, number>;
	}

	let agent = $derived<AgentData | null>(
		$uiStore.selectedAgentId
			? (($simulationStore.agents as Record<string, AgentData>)[$uiStore.selectedAgentId] ?? null)
			: null
	);
	let factions = $derived(($simulationStore.factions ?? {}) as Record<string, FactionData>);

	const ITEM_EMOJIS: Record<string, string> = {
		berries: '🫐',
		wood: '🪵',
		stone: '🪨'
	};

	function getEmoji(item: string): string {
		return ITEM_EMOJIS[item.toLowerCase()] ?? '📦';
	}

	function truncatePrompt(text: string | undefined): string {
		if (!text) return '—';
		if (text.length <= 150) return text;
		return text.slice(0, 150) + '...';
	}

	function getBarColor(stat: string): string {
		switch (stat) {
			case 'hunger':
				return '#f44336';
			case 'thirst':
				return '#2196F3';
			case 'energy':
				return '#FF9800';
			case 'health':
				return '#4CAF50';
			default:
				return '#fff';
		}
	}
</script>

{#if $uiStore.showInspector && agent}
	<div class="inspector">
		<button class="close" onclick={() => uiStore.deselectAgent()} aria-label="Close inspector"
			>×</button
		>
		<h3 class="title">Agent {agent.name ?? agent.id ?? $uiStore.selectedAgentId}</h3>

		<details class="section" open>
			<summary>Vital Signs</summary>
			<div class="section-body">
				{#each ['hunger', 'thirst', 'energy', 'health'] as stat (stat)}
					{@const value = Math.max(
						0,
						Math.min(100, Math.round((agent[stat as keyof AgentData] as number) ?? 0))
					)}
					<div class="stat-row">
						<span class="stat-label">{stat.charAt(0).toUpperCase() + stat.slice(1)}</span>
						<div class="stat-bar-bg">
							<div
								class="stat-bar-fill"
								style="width: {value}%; background-color: {getBarColor(stat)};"
							></div>
						</div>
						<span class="stat-value">{value}</span>
					</div>
				{/each}
			</div>
		</details>

		<details class="section">
			<summary>Identity</summary>
			<div class="section-body">
				<div class="kv-row">
					<span class="kv-key">Role</span><span class="kv-value">{agent.role ?? '—'}</span>
				</div>
				<div class="kv-row">
					<span class="kv-key">Sex</span><span class="kv-value">{agent.sex ?? '—'}</span>
				</div>
				<div class="kv-row">
					<span class="kv-key">Age</span><span class="kv-value"
						>{agent.age ?? 0} / {agent.max_age ?? 0} ticks</span
					>
				</div>
			</div>
		</details>

		<details class="section">
			<summary>Attributes</summary>
			<div class="section-body">
				<div class="kv-row">
					<span class="kv-key">Strength</span><span class="kv-value">{agent.strength ?? 0}</span>
				</div>
				<div class="kv-row">
					<span class="kv-key">Intelligence</span><span class="kv-value"
						>{agent.intelligence ?? 0}</span
					>
				</div>
				<div class="kv-row">
					<span class="kv-key">Sociability</span><span class="kv-value"
						>{agent.sociability ?? 0}</span
					>
				</div>
				<div class="kv-row">
					<span class="kv-key">Speed</span><span class="kv-value">{agent.speed ?? 0}</span>
				</div>
			</div>
		</details>

		<details class="section">
			<summary>Inventory</summary>
			<div class="section-body">
				{#if agent.inventory && Object.keys(agent.inventory).length > 0}
					{#each Object.entries(agent.inventory) as [item, count] (item)}
						<div class="kv-row">
							<span class="kv-key">{getEmoji(item)} {item}</span>
							<span class="kv-value">{count}</span>
						</div>
					{/each}
				{:else}
					<p class="empty">(empty)</p>
				{/if}
			</div>
		</details>

		<details class="section">
			<summary>Monologue</summary>
			<div class="section-body">
				{#if agent.monologue_history && agent.monologue_history.length > 0}
					<ul class="monologue-list">
						{#each agent.monologue_history.slice(-5) as thought (thought)}
							<li>{thought}</li>
						{/each}
					</ul>
				{:else}
					<p class="empty">(no thoughts)</p>
				{/if}
			</div>
		</details>

		<details class="section">
			<summary>Relationships</summary>
			<div class="section-body">
				{#if agent.relationships && Object.keys(agent.relationships).length > 0}
					{#each Object.entries(agent.relationships) as [otherId, rel] (otherId)}
						{@const other = ($simulationStore.agents as Record<string, AgentData>)?.[otherId]}
						<div class="kv-row">
							<span class="kv-key">{other?.name ?? otherId}</span>
							<span class="kv-value"
								>count:{rel.interaction_count} score:{rel.score.toFixed(2)}</span
							>
						</div>
					{/each}
				{:else}
					<p class="empty">(no relationships yet)</p>
				{/if}
			</div>
		</details>

		<details class="section">
			<summary>Faction</summary>
			<div class="section-body">
				{#if agent.faction_id}
					{@const faction = factions[agent.faction_id]}
					<div class="kv-row">
						<span class="kv-key">Name</span>
						<span class="kv-value" style="display:flex;align-items:center;gap:6px;">
							{#if faction}
								<span
									style="width:12px;height:12px;border-radius:50%;background:{faction.color};display:inline-block;"
								></span>
								{faction.name}
							{:else}
								{agent.faction_id}
							{/if}
						</span>
					</div>
				{:else}
					<p class="empty">(not in a faction)</p>
				{/if}
			</div>
		</details>

		<details class="section">
			<summary>Knowledge</summary>
			<div class="section-body">
				{#if agent.knowledge && Object.keys(agent.knowledge).length > 0}
					{#each Object.entries(agent.knowledge) as [k, v] (k)}
						<div class="kv-row">
							<span class="kv-key">{k}</span>
							<span class="kv-value">{JSON.stringify(v)}</span>
						</div>
					{/each}
				{:else}
					<p class="empty">(no special knowledge)</p>
				{/if}
			</div>
		</details>

		<details class="section">
			<summary>Child Status</summary>
			<div class="section-body">
				{#if agent.is_child}
					<div class="kv-row">
						<span class="kv-key">Status</span>
						<span class="kv-value">Child</span>
					</div>
					<div class="kv-row">
						<span class="kv-key">Parent</span>
						<span class="kv-value">{agent.parent_id ?? '—'}</span>
					</div>
					<div class="kv-row">
						<span class="kv-key">Maturity</span>
						<span class="kv-value">{agent.age ?? 0} / {agent.maturity_age ?? 0}</span>
					</div>
				{:else}
					<p class="empty">Adult</p>
				{/if}
			</div>
		</details>

		<details class="section">
			<summary>Prompt</summary>
			<div class="section-body">
				<p class="prompt-text">{truncatePrompt(agent.system_prompt)}</p>
			</div>
		</details>
	</div>
{/if}

<style>
	.inspector {
		position: fixed;
		right: 8px;
		top: 8px;
		width: 260px;
		max-height: calc(100vh - 16px);
		overflow-y: auto;
		background: rgba(0, 0, 0, 0.85);
		color: #fff;
		padding: 16px;
		border-radius: 8px;
		font-family:
			system-ui,
			-apple-system,
			sans-serif;
		font-size: 13px;
		z-index: 20;
		backdrop-filter: blur(4px);
	}

	.close {
		position: absolute;
		top: 8px;
		right: 12px;
		background: none;
		border: none;
		color: #fff;
		font-size: 22px;
		line-height: 1;
		cursor: pointer;
		opacity: 0.7;
		transition: opacity 0.15s;
	}

	.close:hover {
		opacity: 1;
	}

	.title {
		margin: 0 0 12px;
		font-size: 15px;
		font-weight: 600;
	}

	.section {
		border-top: 1px solid rgba(255, 255, 255, 0.1);
		padding: 8px 0;
	}

	.section:first-of-type {
		border-top: none;
	}

	.section summary {
		font-weight: 600;
		font-size: 13px;
		cursor: pointer;
		user-select: none;
		list-style: none;
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.section summary::-webkit-details-marker {
		display: none;
	}

	.section summary::before {
		content: '▸';
		font-size: 12px;
		color: #aaa;
		transition: transform 0.15s;
		display: inline-block;
	}

	.section[open] > summary::before {
		transform: rotate(90deg);
	}

	.section-body {
		margin-top: 8px;
		padding-left: 4px;
	}

	.stat-row {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 6px;
	}

	.stat-row:last-child {
		margin-bottom: 0;
	}

	.stat-label {
		width: 50px;
		font-size: 11px;
		color: #aaa;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		flex-shrink: 0;
	}

	.stat-bar-bg {
		height: 8px;
		background: rgba(255, 255, 255, 0.1);
		border-radius: 4px;
		flex: 1;
		overflow: hidden;
	}

	.stat-bar-fill {
		height: 100%;
		border-radius: 4px;
		transition: width 0.3s;
	}

	.stat-value {
		width: 28px;
		text-align: right;
		font-size: 12px;
		font-weight: 600;
		flex-shrink: 0;
	}

	.kv-row {
		display: flex;
		justify-content: space-between;
		margin-bottom: 4px;
		font-size: 12px;
	}

	.kv-row:last-child {
		margin-bottom: 0;
	}

	.kv-key {
		color: #aaa;
	}

	.kv-value {
		font-weight: 500;
	}

	.empty {
		margin: 0;
		font-style: italic;
		color: #888;
		font-size: 12px;
	}

	.monologue-list {
		margin: 0;
		padding-left: 14px;
		font-size: 12px;
		color: #bbb;
		line-height: 1.5;
	}

	.monologue-list li {
		margin-bottom: 2px;
	}

	.monologue-list li:last-child {
		margin-bottom: 0;
	}

	.prompt-text {
		margin: 0;
		font-size: 11px;
		color: #bbb;
		line-height: 1.5;
		white-space: pre-wrap;
		word-break: break-word;
	}
</style>
