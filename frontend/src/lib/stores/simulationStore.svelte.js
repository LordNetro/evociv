import { writable } from 'svelte/store';

/** @typedef {{ tick: number, agents: Record<string, any>, tiles: Array<{x: number, y: number, resource_type: string|null, amount: number}>, metrics: { population: number, avg_hunger: number, avg_thirst: number, avg_health: number, avg_energy: number }, events: Array<{ event_id: string, type: string, severity: string, description: string, tick: number }>, connected: boolean }} SimulationState */

const INITIAL_STATE = {
	tick: 0,
	agents: {},
	tiles: [],
	metrics: { population: 0, avg_hunger: 0, avg_thirst: 0, avg_health: 0, avg_energy: 0 },
	/** @type {Array<any>} */
	events: [],
	connected: false
};

function createSimulationStore() {
	const { subscribe, set, update } = writable({ ...INITIAL_STATE });

	return {
		subscribe,
		/** @param {any} data */
		updateFromSnapshot(data) {
			update((state) => {
				// Accumulate events (keep last 100)
				const newEvents = data.events ?? [];
				const allEvents = [...state.events, ...newEvents];
				const MAX_EVENTS = 100;
				const trimmed = allEvents.length > MAX_EVENTS ? allEvents.slice(-MAX_EVENTS) : allEvents;

				return {
					...state,
					tick: data.tick ?? state.tick,
					agents: data.agents ?? state.agents,
					tiles: data.tiles ?? state.tiles,
					metrics: data.metrics ?? state.metrics,
					events: trimmed
				};
			});
		},
		/** @param {boolean} connected */
		setConnected(connected) {
			update((state) => ({ ...state, connected }));
		},
		reset() {
			set({ ...INITIAL_STATE });
		}
	};
}

export const simulationStore = createSimulationStore();
