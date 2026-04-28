<script lang="ts">
  import { simulationStore } from '$lib/stores/simulationStore.svelte.js';
  import { uiStore } from '$lib/stores/uiStore.svelte.js';
</script>

<div class="hud">
  <div class="badge" class:connected={$simulationStore.connected}>
    {$simulationStore.connected ? 'Connected' : 'Disconnected'}
  </div>
  <div class="stat">Tick: {$simulationStore.tick}</div>
  <div class="stat">Population: {$simulationStore.metrics.population}</div>
  <button class="btn" onclick={() => uiStore.setPaused(!$uiStore.paused)}>
    {$uiStore.paused ? 'Resume' : 'Pause'}
  </button>
</div>

<style>
  .hud {
    position: fixed;
    top: 8px;
    left: 8px;
    display: flex;
    gap: 12px;
    align-items: center;
    background: rgba(0, 0, 0, 0.75);
    color: #fff;
    padding: 8px 14px;
    border-radius: 8px;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 14px;
    z-index: 10;
    backdrop-filter: blur(4px);
  }

  .badge {
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 4px;
    background: rgba(244, 67, 54, 0.25);
    color: #f44336;
  }

  .badge.connected {
    background: rgba(76, 175, 80, 0.25);
    color: #4caf50;
  }

  .stat {
    color: #ddd;
  }

  .btn {
    cursor: pointer;
    background: rgba(255, 255, 255, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: #fff;
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 13px;
    transition: background 0.15s;
  }

  .btn:hover {
    background: rgba(255, 255, 255, 0.25);
  }
</style>
