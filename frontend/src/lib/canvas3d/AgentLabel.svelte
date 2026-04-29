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
	let bubble = $derived(canvas3dStore.dialogueBubbles[agent.id ?? '']);
</script>

{#if pos}
	<HTML position={[pos.x + 0.5, 1.5, pos.y + 0.5]} distanceFactor={10}>
		<div class="label-wrapper">
			{#if bubble}
				{#if bubble.type === 'speech'}
					<div class="speech-bubble">
						<span class="bubble-text">{bubble.text}</span>
						<div class="bubble-tail"></div>
					</div>
				{:else}
					<div class="thought-bubble">
						<span class="bubble-text">{bubble.text}</span>
						<div class="thought-tail"></div>
					</div>
				{/if}
			{/if}
			<div class="agent-label">
				<span class="name">{agent.name ?? agent.id ?? ''}</span>
				{#if agent.current_action_emoji}
					<span class="emoji">{agent.current_action_emoji}</span>
				{/if}
			</div>
		</div>
	</HTML>
{/if}

<style>
	.label-wrapper {
		display: flex;
		flex-direction: column;
		align-items: center;
		transform: translate(-50%, -100%);
		gap: 4px;
	}

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
		display: flex;
		gap: 4px;
		align-items: center;
	}

	.speech-bubble,
	.thought-bubble {
		position: relative;
		padding: 6px 10px;
		border-radius: 12px;
		font-size: 11px;
		font-family: system-ui, sans-serif;
		max-width: 180px;
		text-wrap: balance;
		overflow: hidden;
		pointer-events: none;
		user-select: none;
		animation: bubbleIn 0.2s ease-out;
	}

	.speech-bubble {
		background: #fff;
		color: #111;
		border: 2px solid #111;
	}

	.thought-bubble {
		background: #f0f4f8;
		color: #333;
		border: 2px dashed #666;
		font-style: italic;
		border-radius: 16px;
	}

	.bubble-text {
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.bubble-tail {
		position: absolute;
		bottom: -8px;
		left: 50%;
		transform: translateX(-50%);
		width: 0;
		height: 0;
		border-left: 8px solid transparent;
		border-right: 8px solid transparent;
		border-top: 8px solid #111;
	}

	.bubble-tail::after {
		content: '';
		position: absolute;
		left: -6px;
		top: -10px;
		width: 0;
		height: 0;
		border-left: 6px solid transparent;
		border-right: 6px solid transparent;
		border-top: 6px solid #fff;
	}

	.thought-tail {
		position: absolute;
		bottom: -10px;
		left: 50%;
		transform: translateX(-50%);
		width: 10px;
		height: 10px;
		background: #f0f4f8;
		border: 2px dashed #666;
		border-radius: 50%;
	}

	.thought-tail::after {
		content: '';
		position: absolute;
		bottom: -8px;
		left: 50%;
		transform: translateX(-50%);
		width: 6px;
		height: 6px;
		background: #f0f4f8;
		border: 2px dashed #666;
		border-radius: 50%;
	}

	@keyframes bubbleIn {
		from {
			opacity: 0;
			transform: translateY(8px) scale(0.9);
		}
		to {
			opacity: 1;
			transform: translateY(0) scale(1);
		}
	}
</style>
