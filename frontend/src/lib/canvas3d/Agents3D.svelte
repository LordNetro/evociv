<script lang="ts">
	import { T, useTask } from '@threlte/core';
	import { uiStore } from '$lib/stores/uiStore.svelte.js';
	import { canvas3dStore } from './canvas3dStore.svelte.js';

	interface AgentState {
		id?: string;
		position?: [number, number];
		role?: string;
		faction_id?: string;
		is_child?: boolean;
	}

	interface Props {
		agents: Record<string, AgentState>;
		factions?: Record<string, { color: string }>;
	}

	let { agents, factions = {} }: Props = $props();

	const ROLE_COLORS: Record<string, string> = {
		gatherer: '#4CAF50',
		builder: '#FF9800',
		scout: '#2196F3',
		explorer: '#9C27B0',
		warrior: '#F44336',
		default: '#9E9E9E'
	};

	// tick() runs every frame via Threlte's render loop — safe to read/write agentPositions
	useTask((delta) => {
		canvas3dStore.tick(delta);
	});

	// updateTargets only writes targetPositions (does NOT read agentPositions) — no reactive cycle
	$effect(() => {
		canvas3dStore.updateTargets({ agents });
	});

	function getColor(role: string | undefined): string {
		return ROLE_COLORS[role ?? ''] ?? ROLE_COLORS.default;
	}

	function getFactionColor(factionId: string | undefined): string | null {
		if (!factionId) return null;
		return factions[factionId]?.color ?? null;
	}

	function handleClick(agentId: string) {
		uiStore.selectAgent(agentId);
	}

	function agentEntries() {
		return Object.entries(agents);
	}
</script>

{#each agentEntries() as [id, agent] (id)}
	{@const pos = canvas3dStore.agentPositions[id]}
	{@const scale = agent.is_child ? 0.6 : 1}
	{#if pos}
		{@const factionColor = getFactionColor(agent.faction_id)}
		<T.Group position={[pos.x + 0.5, 0.5, pos.y + 0.5]} scale={[scale, scale, scale]}>
			{#if factionColor}
				<T.Mesh rotation={[-Math.PI / 2, 0, 0]}>
					<T.RingGeometry args={[0.4, 0.45, 32]} />
					<T.MeshStandardMaterial color={factionColor} side={2} />
				</T.Mesh>
			{/if}
			<T.Mesh on:click={() => handleClick(id)} userData={{ agentId: id }}>
				<T.SphereGeometry args={[0.35]} />
				<T.MeshStandardMaterial color={getColor(agent.role)} />
			</T.Mesh>
		</T.Group>
	{/if}
{/each}
