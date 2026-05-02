<script lang="ts">
	import { T, useTask } from '@threlte/core';
	import { useInteractivity } from '@threlte/extras';
	import { MeshStandardMaterial, Color } from 'three';
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

	const ROLE_MATERIALS: Record<string, MeshStandardMaterial> = {};

	function injectFresnel(material: MeshStandardMaterial) {
		material.userData.uTime = { value: 0 };
		material.onBeforeCompile = (shader) => {
			shader.uniforms.uTime = material.userData.uTime;

			shader.vertexShader = shader.vertexShader.replace(
				'#include <common>',
				`#include <common>
				varying vec3 vWorldPosition;
				varying vec3 vWorldNormal;
				uniform float uTime;`
			);
			shader.vertexShader = shader.vertexShader.replace(
				'#include <begin_vertex>',
				`#include <begin_vertex>
				float phase = modelMatrix[3][0] * 3.14159 + modelMatrix[3][2] * 3.14159;
				float bob = sin(uTime * 3.0 + phase) * 0.03;
				transformed.y += bob;`
			);
			shader.vertexShader = shader.vertexShader.replace(
				'#include <worldpos_vertex>',
				`#include <worldpos_vertex>
				vWorldPosition = (modelMatrix * vec4(transformed, 1.0)).xyz;
				vWorldNormal = normalize(normalMatrix * normal);`
			);
			shader.fragmentShader = shader.fragmentShader.replace(
				'#include <common>',
				`#include <common>
				varying vec3 vWorldPosition;
				varying vec3 vWorldNormal;
				uniform vec3 uFresnelColor;
				uniform float uFresnelPower;`
			);
			shader.fragmentShader = shader.fragmentShader.replace(
				'#include <dithering_fragment>',
				`#include <dithering_fragment>
				vec3 viewDir = normalize(cameraPosition - vWorldPosition);
				float fresnel = pow(1.0 - max(dot(vWorldNormal, viewDir), 0.0), uFresnelPower);
				gl_FragColor.rgb += uFresnelColor * fresnel * 0.6;`
			);
			shader.uniforms.uFresnelColor = { value: new Color(0xffffff) };
			shader.uniforms.uFresnelPower = { value: 3.0 };
		};
	}

	function getMaterial(role: string | undefined): MeshStandardMaterial {
		const colorHex = ROLE_COLORS[role ?? ''] ?? ROLE_COLORS.default;
		if (!ROLE_MATERIALS[colorHex]) {
			const mat = new MeshStandardMaterial({ color: colorHex });
			injectFresnel(mat);
			ROLE_MATERIALS[colorHex] = mat;
		}
		return ROLE_MATERIALS[colorHex];
	}

	// tick() runs every frame via Threlte's render loop — safe to read/write agentPositions
	useTask((delta) => {
		canvas3dStore.tick(delta);
		for (const mat of Object.values(ROLE_MATERIALS)) {
			if (mat.userData.uTime) {
				mat.userData.uTime.value += delta;
			}
		}
	});

	// updateTargets only writes targetPositions (does NOT read agentPositions) — no reactive cycle
	$effect(() => {
		canvas3dStore.updateTargets({ agents });
	});

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
			<T.Mesh
				oncreate={(ref) => {
					const { addInteractiveObject, removeInteractiveObject } = useInteractivity();
					const handler = () => handleClick(id);
					addInteractiveObject(ref, { onclick: handler });
					return () => removeInteractiveObject(ref);
				}}
				userData={{ agentId: id }}
				material={getMaterial(agent.role)}
			>
				<T.SphereGeometry args={[0.35]} />
			</T.Mesh>
		</T.Group>
	{/if}
{/each}
