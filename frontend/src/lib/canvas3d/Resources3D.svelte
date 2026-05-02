<script lang="ts">
	import { T, useTask } from '@threlte/core';
	import {
		InstancedMesh as ThreeInstancedMesh,
		BoxGeometry,
		SphereGeometry,
		CylinderGeometry,
		ConeGeometry,
		DodecahedronGeometry,
		MeshStandardMaterial,
		ShaderMaterial,
		Color,
		Object3D
	} from 'three';
	import { useInteractivity } from '@threlte/extras';
	import treeVert from '$lib/shaders/tree.vert.glsl?raw';
	import treeFrag from '$lib/shaders/tree.frag.glsl?raw';

	interface TileData {
		x: number;
		y: number;
		resource_type: string | null;
		amount: number;
	}

	interface Props {
		resources: TileData[];
		onHarvest?: (x: number, y: number, type: string) => void;
	}

	let { resources, onHarvest }: Props = $props();

	const RESOURCE_GEO = {
		tree_trunk: new CylinderGeometry(0.08, 0.1, 0.3),
		tree_canopy: new ConeGeometry(0.4, 0.8),
		berry: new SphereGeometry(0.2),
		stone: new BoxGeometry(0.35, 0.25, 0.35),
		iron_ore: new DodecahedronGeometry(0.18),
		clay: new SphereGeometry(0.15),
		sand: new BoxGeometry(0.3, 0.15, 0.3),
		fiber: new CylinderGeometry(0.03, 0.03, 0.4)
	};

	const RESOURCE_COLORS: Record<string, string> = {
		tree_trunk: '#5d4037',
		tree_canopy: '#2e7d32',
		berry: '#e53935',
		stone: '#9E9E9E',
		iron_ore: '#5c6bc0',
		clay: '#d7ccc8',
		sand: '#fff59d',
		fiber: '#a5d6a7'
	};

	// Shared stock materials
	const trunkMat = new MeshStandardMaterial({ color: RESOURCE_COLORS.tree_trunk });
	const berryMat = new MeshStandardMaterial({ color: RESOURCE_COLORS.berry });
	const stoneMat = new MeshStandardMaterial({ color: RESOURCE_COLORS.stone });
	const ironOreMat = new MeshStandardMaterial({ color: RESOURCE_COLORS.iron_ore });
	const clayMat = new MeshStandardMaterial({ color: RESOURCE_COLORS.clay });
	const sandMat = new MeshStandardMaterial({ color: RESOURCE_COLORS.sand });
	const fiberMat = new MeshStandardMaterial({ color: RESOURCE_COLORS.fiber });

	// Tree canopy sway shader material
	const treeCanopyMat = new ShaderMaterial({
		uniforms: {
			uTime: { value: 0 },
			uWindStrength: { value: 0.08 },
			uWindFrequency: { value: 1.5 },
			uColor: { value: new Color(RESOURCE_COLORS.tree_canopy) },
			uShadowColor: { value: new Color(0x1b5e20) }
		},
		vertexShader: treeVert,
		fragmentShader: treeFrag
	});

	useTask((delta) => {
		treeCanopyMat.uniforms.uTime.value += delta;
	});

	// Derived filtered arrays per resource type
	let trees = $derived(resources.filter((r) => r.resource_type === 'tree'));
	let berries = $derived(resources.filter((r) => r.resource_type === 'berries'));
	let stones = $derived(resources.filter((r) => r.resource_type === 'stone'));
	let ironOres = $derived(resources.filter((r) => r.resource_type === 'iron_ore'));
	let clays = $derived(resources.filter((r) => r.resource_type === 'clay'));
	let sands = $derived(resources.filter((r) => r.resource_type === 'sand'));
	let fibers = $derived(resources.filter((r) => r.resource_type === 'fiber'));

	// Harvest diff detection — NOT $state to avoid infinite loops
	let prevAmounts: Record<string, number> = {};
	let prevResourcesJson = '';

	$effect(() => {
		const json = JSON.stringify(resources.map((r) => `${r.x},${r.y}:${r.amount}`));
		if (json === prevResourcesJson) return;
		prevResourcesJson = json;

		const newPrev: Record<string, number> = {};
		for (const r of resources) {
			const key = `${r.x},${r.y}`;
			const prev = prevAmounts[key];
			if (prev !== undefined && r.amount < prev && onHarvest) {
				onHarvest(r.x, r.y, r.resource_type ?? 'unknown');
			}
			newPrev[key] = r.amount;
		}
		prevAmounts = newPrev;
	});

	// Instance mesh refs
	let treeTrunkRef: ThreeInstancedMesh | undefined = $state();
	let treeCanopyRef: ThreeInstancedMesh | undefined = $state();
	let berryRef: ThreeInstancedMesh | undefined = $state();
	let stoneRef: ThreeInstancedMesh | undefined = $state();
	let ironOreRef: ThreeInstancedMesh | undefined = $state();
	let clayRef: ThreeInstancedMesh | undefined = $state();
	let sandRef: ThreeInstancedMesh | undefined = $state();
	let fiberRef: ThreeInstancedMesh | undefined = $state();

	// Resource lookup arrays for raycast instanceId mapping
	const resourceArrays = {
		tree_trunk: () => trees,
		tree_canopy: () => trees,
		berry: () => berries,
		stone: () => stones,
		iron_ore: () => ironOres,
		clay: () => clays,
		sand: () => sands,
		fiber: () => fibers
	};

	const dummy = new Object3D();

	function updateInstancedMesh(
		mesh: ThreeInstancedMesh | undefined,
		items: TileData[],
		yOffset: number
	) {
		if (!mesh) return;
		mesh.count = items.length;
		for (let i = 0; i < items.length; i++) {
			const item = items[i];
			dummy.position.set(item.x + 0.5, yOffset, item.y + 0.5);
			dummy.updateMatrix();
			mesh.setMatrixAt(i, dummy.matrix);
		}
		mesh.instanceMatrix.needsUpdate = true;
		mesh.frustumCulled = false;
	}

	// Trunk at y=0.25 (matches original: group y=0.1 + mesh y=0.15)
	// Canopy at y=0.6 (matches original: group y=0.1 + mesh y=0.5)
	$effect(() => updateInstancedMesh(treeTrunkRef, trees, 0.25));
	$effect(() => updateInstancedMesh(treeCanopyRef, trees, 0.6));
	$effect(() => updateInstancedMesh(berryRef, berries, 0.2));
	$effect(() => updateInstancedMesh(stoneRef, stones, 0.2));
	$effect(() => updateInstancedMesh(ironOreRef, ironOres, 0.18));
	$effect(() => updateInstancedMesh(clayRef, clays, 0.15));
	$effect(() => updateInstancedMesh(sandRef, sands, 0.15));
	$effect(() => updateInstancedMesh(fiberRef, fibers, 0.25));

	function handleResourceClick(type: string, instanceId: number) {
		const arr = resourceArrays[type as keyof typeof resourceArrays]();
		const resource = arr[instanceId];
		if (resource) {
			// eslint-disable-next-line no-console
			console.log('Clicked resource:', resource);
		}
	}

	function setupInteractivity(ref: ThreeInstancedMesh, type: string) {
		const { addInteractiveObject, removeInteractiveObject } = useInteractivity();
		addInteractiveObject(ref, {
			onclick: (e: unknown) => {
				const event = e as { intersection?: { instanceId?: number } };
				const instanceId = event.intersection?.instanceId;
				if (instanceId !== undefined) {
					handleResourceClick(type, instanceId);
				}
			}
		});
		return () => removeInteractiveObject(ref);
	}
</script>

<!-- Trees: trunk + canopy -->
{#if trees.length > 0}
	<T.InstancedMesh
		bind:ref={treeTrunkRef}
		oncreate={(ref) => setupInteractivity(ref, 'tree_trunk')}
	>
		<T is={RESOURCE_GEO.tree_trunk} />
		<T is={trunkMat} />
	</T.InstancedMesh>
	<T.InstancedMesh
		bind:ref={treeCanopyRef}
		oncreate={(ref) => setupInteractivity(ref, 'tree_canopy')}
	>
		<T is={RESOURCE_GEO.tree_canopy} />
		<T is={treeCanopyMat} />
	</T.InstancedMesh>
{/if}

{#if berries.length > 0}
	<T.InstancedMesh bind:ref={berryRef} oncreate={(ref) => setupInteractivity(ref, 'berry')}>
		<T is={RESOURCE_GEO.berry} />
		<T is={berryMat} />
	</T.InstancedMesh>
{/if}

{#if stones.length > 0}
	<T.InstancedMesh bind:ref={stoneRef} oncreate={(ref) => setupInteractivity(ref, 'stone')}>
		<T is={RESOURCE_GEO.stone} />
		<T is={stoneMat} />
	</T.InstancedMesh>
{/if}

{#if ironOres.length > 0}
	<T.InstancedMesh bind:ref={ironOreRef} oncreate={(ref) => setupInteractivity(ref, 'iron_ore')}>
		<T is={RESOURCE_GEO.iron_ore} />
		<T is={ironOreMat} />
	</T.InstancedMesh>
{/if}

{#if clays.length > 0}
	<T.InstancedMesh bind:ref={clayRef} oncreate={(ref) => setupInteractivity(ref, 'clay')}>
		<T is={RESOURCE_GEO.clay} />
		<T is={clayMat} />
	</T.InstancedMesh>
{/if}

{#if sands.length > 0}
	<T.InstancedMesh bind:ref={sandRef} oncreate={(ref) => setupInteractivity(ref, 'sand')}>
		<T is={RESOURCE_GEO.sand} />
		<T is={sandMat} />
	</T.InstancedMesh>
{/if}

{#if fibers.length > 0}
	<T.InstancedMesh bind:ref={fiberRef} oncreate={(ref) => setupInteractivity(ref, 'fiber')}>
		<T is={RESOURCE_GEO.fiber} />
		<T is={fiberMat} />
	</T.InstancedMesh>
{/if}
