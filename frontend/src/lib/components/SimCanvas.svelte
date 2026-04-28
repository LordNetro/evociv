<script lang="ts">
  import { Engine, type EngineConfig } from '$lib/canvas/engine';
  import { simulationStore } from '$lib/stores/simulationStore.svelte.js';
  import { uiStore } from '$lib/stores/uiStore.svelte.js';

  interface Props {
    config?: EngineConfig;
  }

  let { config = { tileSize: 32, gridWidth: 50, gridHeight: 50 } }: Props = $props();
  let canvas: HTMLCanvasElement;
  let engine: Engine | null = null;

  $effect(() => {
    engine = new Engine(canvas, config);

    const doResize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      if (rect) engine!.setSize(rect.width, rect.height);
    };

    doResize();
    window.addEventListener('resize', doResize);

    engine.onAgentClick = (agentId: string) => {
      uiStore.selectAgent(agentId);
    };

    engine.start();

    return () => {
      window.removeEventListener('resize', doResize);
      engine?.destroy();
      engine = null;
    };
  });

  // Feed snapshot data to engine
  $effect(() => {
    const snapshot = $simulationStore;
    engine?.updateSnapshot(snapshot);
  });
</script>

<canvas bind:this={canvas} class="game-canvas"></canvas>

<style>
  .game-canvas {
    display: block;
    width: 100%;
    height: 100%;
    cursor: grab;
  }
  .game-canvas:active {
    cursor: grabbing;
  }
</style>
