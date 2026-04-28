<script lang="ts">
	import { simulationStore } from '$lib/stores/simulationStore.svelte.js';
	import Chart from 'chart.js/auto';

	let canvas: HTMLCanvasElement;
	let chart: Chart | null = null;
	const maxDataPoints = 100;

	$effect(() => {
		chart = new Chart(canvas, {
			type: 'line',
			data: {
				labels: [],
				datasets: [
					{
						label: 'Population',
						data: [],
						borderColor: '#4CAF50',
						backgroundColor: '#4CAF50',
						pointRadius: 0,
						tension: 0.3
					},
					{
						label: 'Avg Hunger',
						data: [],
						borderColor: '#FF9800',
						backgroundColor: '#FF9800',
						pointRadius: 0,
						tension: 0.3
					},
					{
						label: 'Avg Thirst',
						data: [],
						borderColor: '#2196F3',
						backgroundColor: '#2196F3',
						pointRadius: 0,
						tension: 0.3
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: false,
				interaction: { intersect: false, mode: 'index' },
				scales: {
					x: { display: false },
					y: {
						beginAtZero: true,
						grid: { color: 'rgba(255,255,255,0.1)' },
						ticks: { color: '#ccc' }
					}
				},
				plugins: {
					legend: { labels: { color: '#eee' } }
				}
			}
		});

		return () => {
			chart?.destroy();
			chart = null;
		};
	});

	$effect(() => {
		const store = $simulationStore;
		if (!chart) return;

		const labels = chart.data.labels as string[];
		const datasets = chart.data.datasets;

		labels.push(String(store.tick));
		datasets[0].data.push(store.metrics.population);
		datasets[1].data.push(store.metrics.avg_hunger);
		datasets[2].data.push(store.metrics.avg_thirst);

		if (labels.length > maxDataPoints) {
			labels.shift();
			datasets.forEach((d) => (d.data as number[]).shift());
		}

		chart.update('none');
	});
</script>

<div class="chart-container">
	<canvas bind:this={canvas}></canvas>
</div>

<style>
	.chart-container {
		position: fixed;
		bottom: 8px;
		left: 8px;
		width: 300px;
		height: 200px;
		background: rgba(0, 0, 0, 0.75);
		border-radius: 8px;
		padding: 8px;
		z-index: 5;
		backdrop-filter: blur(4px);
	}

	canvas {
		width: 100%;
		height: 100%;
	}
</style>
