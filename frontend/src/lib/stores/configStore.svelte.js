import { writable } from 'svelte/store';

/**
 * @typedef {{ gridWidth: number, gridHeight: number, tileSize: number, tickRate: number, wsUrl: string }} ConfigState
 */

const DEFAULT_CONFIG = {
	gridWidth: 80,
	gridHeight: 80,
	tileSize: 32,
	tickRate: 0.1,
	wsUrl: 'ws://127.0.0.1:8765/ws'
};

function createConfigStore() {
	const { subscribe, update } = writable({ ...DEFAULT_CONFIG });

	return {
		subscribe,
		/** @param {Partial<ConfigState>} partial */
		updateConfig(partial) {
			update((state) => ({ ...state, ...partial }));
		},
		reset() {
			update(() => ({ ...DEFAULT_CONFIG }));
		}
	};
}

export const configStore = createConfigStore();
