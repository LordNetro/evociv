<script lang="ts">
  import { simulationStore } from '$lib/stores/simulationStore.svelte.js';

  interface EventData {
    event_id: string;
    type: string;
    severity: 'info' | 'warning' | 'critical';
    description: string;
    tick: number;
  }

  let filter = $state<'all' | 'info' | 'warning' | 'critical'>('all');
  let logEl: HTMLDivElement;

  let events = $derived<EventData[]>(
    filter === 'all'
      ? ($simulationStore.events as EventData[])
      : ($simulationStore.events as EventData[]).filter((e) => e.severity === filter)
  );

  $effect(() => {
    // Auto-scroll to bottom when events change
    if (logEl) {
      requestAnimationFrame(() => {
        logEl.scrollTop = logEl.scrollHeight;
      });
    }
  });
</script>

<div class="event-log">
  <div class="header">
    <strong>Event Log</strong>
    <select bind:value={filter}>
      <option value="all">All</option>
      <option value="info">Info</option>
      <option value="warning">Warning</option>
      <option value="critical">Critical</option>
    </select>
  </div>
  <div class="log" bind:this={logEl}>
    {#each events as event, i (i)}
      <div
        class="event"
        class:critical={event.severity === 'critical'}
        class:warning={event.severity === 'warning'}
      >
        <span class="type">[{event.type ?? 'event'}]</span>
        <span class="desc">{event.description ?? ''}</span>
      </div>
    {/each}
  </div>
</div>

<style>
  .event-log {
    position: fixed;
    bottom: 8px;
    right: 8px;
    width: 340px;
    height: 220px;
    background: rgba(0, 0, 0, 0.85);
    color: #fff;
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 12px;
    z-index: 10;
    backdrop-filter: blur(4px);
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .log {
    flex: 1;
    overflow-y: auto;
    padding: 8px 12px;
  }

  .event {
    margin-bottom: 4px;
    line-height: 1.4;
  }

  .type {
    color: #aaa;
    margin-right: 6px;
    font-weight: 500;
  }

  .warning .type {
    color: #ff9800;
  }

  .critical .type {
    color: #f44336;
  }

  .desc {
    color: #ddd;
  }

  select {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 12px;
  }

  select option {
    background: #222;
    color: #fff;
  }
</style>
