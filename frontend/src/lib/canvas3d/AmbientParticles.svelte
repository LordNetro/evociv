<script lang="ts">
	import { T, useTask } from '@threlte/core';
	import { BufferGeometry, Float32BufferAttribute, PointsMaterial, AdditiveBlending } from 'three';

	const COUNT = 300;
	const SPREAD = 50;
	const HEIGHT_VARIANCE = 5;

	const positions = new Float32Array(COUNT * 3);
	const offsets = new Float32Array(COUNT);

	for (let i = 0; i < COUNT; i++) {
		positions[i * 3] = (Math.random() - 0.5) * SPREAD;
		positions[i * 3 + 1] = Math.random() * HEIGHT_VARIANCE;
		positions[i * 3 + 2] = (Math.random() - 0.5) * SPREAD;
		offsets[i] = Math.random() * Math.PI * 2;
	}

	const geometry = new BufferGeometry();
	geometry.setAttribute('position', new Float32BufferAttribute(positions, 3));

	const material = new PointsMaterial({
		color: '#ffffff',
		size: 0.02,
		transparent: true,
		opacity: 0.3,
		depthWrite: false,
		sizeAttenuation: true,
		blending: AdditiveBlending
	});

	let time = 0;

	useTask((delta) => {
		time += delta;
		const posArray = geometry.attributes.position.array as Float32Array;
		for (let i = 0; i < COUNT; i++) {
			const offset = offsets[i];
			posArray[i * 3] += Math.sin(time * 0.5 + offset) * delta * 0.05;
			posArray[i * 3 + 1] += Math.sin(time * 0.3 + offset) * delta * 0.02;
			posArray[i * 3 + 2] += Math.cos(time * 0.5 + offset) * delta * 0.05;
		}
		geometry.attributes.position.needsUpdate = true;
	});
</script>

<T.Points {geometry} {material} />
