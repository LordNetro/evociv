<script lang="ts">
	import { T, useTask } from '@threlte/core';
	import { BufferGeometry, Float32BufferAttribute, PointsMaterial } from 'three';

	interface BurstData {
		id: number;
		x: number;
		y: number;
		type: string;
	}

	interface Props {
		bursts: BurstData[];
		onComplete: (id: number) => void;
	}

	let { bursts, onComplete }: Props = $props();

	const BURST_COLORS: Record<string, string> = {
		berries: '#e53935',
		tree: '#5d4037',
		stone: '#9E9E9E',
		iron_ore: '#616161',
		clay: '#8d6e63',
		sand: '#fdd835',
		fiber: '#66bb6a'
	};

	interface ActiveBurst {
		id: number;
		x: number;
		y: number;
		type: string;
		startTime: number;
		geometry: BufferGeometry;
		material: PointsMaterial;
	}

	let activeBursts = $state<ActiveBurst[]>([]);

	function createBurstGeometry(): BufferGeometry {
		const geometry = new BufferGeometry();
		const positions = new Float32Array(15 * 3);
		for (let i = 0; i < 15; i++) {
			positions[i * 3] = (Math.random() - 0.5) * 0.5;
			positions[i * 3 + 1] = Math.random() * 0.3;
			positions[i * 3 + 2] = (Math.random() - 0.5) * 0.5;
		}
		geometry.setAttribute('position', new Float32BufferAttribute(positions, 3));
		return geometry;
	}

	$effect(() => {
		for (const b of bursts) {
			if (!activeBursts.find((ab) => ab.id === b.id)) {
				const geometry = createBurstGeometry();
				const material = new PointsMaterial({
					color: BURST_COLORS[b.type] ?? '#ffffff',
					size: 0.08,
					transparent: true,
					opacity: 1,
					depthWrite: false,
					sizeAttenuation: true
				});
				activeBursts = [
					...activeBursts,
					{
						id: b.id,
						x: b.x,
						y: b.y,
						type: b.type,
						startTime: performance.now(),
						geometry,
						material
					}
				];
			}
		}
	});

	useTask(() => {
		const now = performance.now();
		const remaining: ActiveBurst[] = [];
		for (const b of activeBursts) {
			const elapsed = (now - b.startTime) / 1000;
			if (elapsed >= 0.5) {
				b.geometry.dispose();
				b.material.dispose();
				onComplete(b.id);
			} else {
				const t = elapsed / 0.5;
				b.material.opacity = 1 - t;
				b.material.size = 0.08 * (1 - t);
				const positions = b.geometry.attributes.position.array as Float32Array;
				for (let i = 0; i < 15; i++) {
					positions[i * 3 + 1] += 0.015;
				}
				b.geometry.attributes.position.needsUpdate = true;
				remaining.push(b);
			}
		}
		if (remaining.length !== activeBursts.length) {
			activeBursts = remaining;
		}
	});
</script>

{#each activeBursts as burst (burst.id)}
	<T.Points position={[burst.x + 0.5, 0.5, burst.y + 0.5]}>
		<T is={burst.geometry} />
		<T is={burst.material} />
	</T.Points>
{/each}
