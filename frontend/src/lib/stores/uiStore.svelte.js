import { writable } from 'svelte/store';

/**
 * @typedef {{ selectedAgentId: string | null, showInspector: boolean, showCharts: boolean, showEventLog: boolean, paused: boolean, speed: number }} UiState
 */

function createUiStore() {
	const { subscribe, update } = writable(
		/** @type {UiState} */ ({
			selectedAgentId: null,
			showInspector: false,
			showCharts: true,
			showEventLog: true,
			paused: false,
			speed: 1
		})
	);

	return {
		subscribe,
		/** @param {string} id */
		selectAgent(id) {
			update((state) => ({ ...state, selectedAgentId: id, showInspector: true }));
		},
		deselectAgent() {
			update((state) => ({ ...state, selectedAgentId: null, showInspector: false }));
		},
		toggleCharts() {
			update((state) => ({ ...state, showCharts: !state.showCharts }));
		},
		toggleEventLog() {
			update((state) => ({ ...state, showEventLog: !state.showEventLog }));
		},
		/** @param {boolean} paused */
		setPaused(paused) {
			update((state) => ({ ...state, paused }));
		},
		/** @param {number} speed */
		setSpeed(speed) {
			update((state) => ({ ...state, speed }));
		}
	};
}

export const uiStore = createUiStore();
