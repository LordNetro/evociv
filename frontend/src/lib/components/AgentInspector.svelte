<script lang="ts">
  import { simulationStore } from '$lib/stores/simulationStore.svelte.js';
  import { uiStore } from '$lib/stores/uiStore.svelte.js';

  interface AgentData {
    id?: string;
    hunger?: number;
    thirst?: number;
    energy?: number;
    health?: number;
    last_thought?: string;
    [key: string]: unknown;
  }

  let agent = $derived<AgentData | null>(
    $uiStore.selectedAgentId
      ? ($simulationStore.agents as Record<string, AgentData>)[$uiStore.selectedAgentId] ?? null
      : null
  );
</script>

{#if $uiStore.showInspector && agent}
  <div class="inspector">
    <button class="close" onclick={() => uiStore.deselectAgent()} aria-label="Close inspector">×</button>
    <h3 class="title">Agent {agent.id ?? $uiStore.selectedAgentId}</h3>

    <div class="stats">
      <div class="stat">
        <span class="label">Hunger</span>
        <span class="value">{agent.hunger ?? 0}</span>
      </div>
      <div class="stat">
        <span class="label">Thirst</span>
        <span class="value">{agent.thirst ?? 0}</span>
      </div>
      <div class="stat">
        <span class="label">Energy</span>
        <span class="value">{agent.energy ?? 0}</span>
      </div>
      <div class="stat">
        <span class="label">Health</span>
        <span class="value">{agent.health ?? 0}</span>
      </div>
    </div>

    <div class="thought">
      <strong>Last Thought</strong>
      <p>{agent.last_thought ?? '—'}</p>
    </div>
  </div>
{/if}

<style>
  .inspector {
    position: fixed;
    right: 8px;
    top: 8px;
    width: 260px;
    background: rgba(0, 0, 0, 0.85);
    color: #fff;
    padding: 16px;
    border-radius: 8px;
    font-family: system-ui, -apple-system, sans-serif;
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

  .stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 12px;
  }

  .stat {
    background: rgba(255, 255, 255, 0.08);
    padding: 6px 8px;
    border-radius: 4px;
    display: flex;
    flex-direction: column;
  }

  .label {
    font-size: 11px;
    color: #aaa;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .value {
    font-size: 14px;
    font-weight: 600;
    margin-top: 2px;
  }

  .thought strong {
    display: block;
    font-size: 12px;
    margin-bottom: 4px;
    color: #ccc;
  }

  .thought p {
    margin: 0;
    font-style: italic;
    color: #bbb;
    line-height: 1.4;
  }
</style>
