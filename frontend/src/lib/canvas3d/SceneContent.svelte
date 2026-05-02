<script lang="ts">
	import { T } from '@threlte/core';
	import { OrbitControls } from '@threlte/extras';
	import KeyboardPan from './KeyboardPan.svelte';
	import { setControls } from './controlsStore';
</script>

<T.PerspectiveCamera
	makeDefault
	position={[35, 35, 35]}
	oncreate={(ref) => {
		ref.lookAt(0, 0, 0);
	}}
>
	<OrbitControls
		enableDamping
		minDistance={5}
		maxDistance={100}
		oncreate={(c) => {
			setControls(c);
		}}
	/>
</T.PerspectiveCamera>

<T.AmbientLight intensity={0.5} />
<T.DirectionalLight position={[10, 20, 10]} intensity={1.0} />

<KeyboardPan />
