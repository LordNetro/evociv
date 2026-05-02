<script lang="ts">
	import { T } from '@threlte/core';
	import { OrbitControls } from '@threlte/extras';
	import * as THREE from 'three';
	import KeyboardPan from './KeyboardPan.svelte';
	import { setControls } from './controlsStore';
</script>

<T.PerspectiveCamera
	makeDefault
	position={[35, 30, 35]}
	fov={50}
	near={0.5}
	far={200}
	oncreate={(ref) => {
		ref.lookAt(25, 0, 25);
	}}
>
	<OrbitControls
		enableDamping
		dampingFactor={0.08}
		minDistance={8}
		maxDistance={120}
		maxPolarAngle={Math.PI / 2.1}
		oncreate={(c) => {
			c.target.set(25, 0, 25);
			setControls(c);
		}}
	/>
</T.PerspectiveCamera>

<!--
	Lighting: hemisphere for ambient + directional for shadows.
	Lower intensity to prevent blowout with ACESFilmicToneMapping + bloom.
-->
<T.HemisphereLight
	args={[new THREE.Color(0x87ceeb), new THREE.Color(0x3a3a5c), 0.6]}
/>

<T.DirectionalLight
	position={[30, 40, 20]}
	intensity={1.2}
	castShadow={true}
>
</T.DirectionalLight>

<!-- Fill light from opposite side to reduce harsh shadows -->
<T.DirectionalLight
	position={[-20, 10, -20]}
	intensity={0.3}
/>

<KeyboardPan />
