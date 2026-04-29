<script lang="ts">
	import { HTML } from '@threlte/extras';
	import { canvas3dStore } from './canvas3dStore.svelte.js';

	interface AgentState {
		id?: string;
		name?: string;
		current_action_emoji?: string;
	}

	interface Props {
		agent: AgentState;
	}

	let { agent }: Props = $props();

	let pos = $derived(canvas3dStore.agentPositions[agent.id ?? '']);
</script>

{#if pos}
	<HTML position={[pos.x + 0.5, 1.5, pos.y + 0.5]} distanceFactor={10}>
		<div class="agent-label">
			<span class="name">{agent.name ?? agent.id ?? ''}</span>
			{#if agent.current_action_emoji}
				<span class="emoji">{agent.current_action_emoji}</span>
			{/if}
		</div>
	</HTML>
{/if}

<style>
	.agent-label {
		pointer-events: none;
		user-select: none;
		background: rgba(0, 0, 0, 0.6);
		color: #fff;
		padding: 2px 6px;
		border-radius: 4px;
		font-size: 11px;
		font-family: system-ui, sans-serif;
		white-space: nowrap;
		transform: translate(-50%, -100%);
		display: flex;
		gap: 4px;
		align-items: center;
	}
</style>
