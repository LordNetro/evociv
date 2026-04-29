import { writable } from 'svelte/store';

/** @typedef {{ tick: number, agents: Record<string, any>, tiles: Array<{x: number, y: number, resource_type: string|null, amount: number}>, metrics: { population: number, avg_hunger: number, avg_thirst: number, avg_health: number, avg_energy: number }, events: Array<{ event_id: string, type: string, severity: string, description: string, tick: number }>, connected: boolean, colony_stats: { population: number, births: number, deaths: number, total_resources: Record<string, number> } | null, factions: Record<string, { id: string, name: string, color: string, member_count: number, shared_resources: Record<string, number> }> }} SimulationState */

const INITIAL_STATE = {
	tick: 0,
	agents: {},
	tiles: [],
	metrics: { population: 0, avg_hunger: 0, avg_thirst: 0, avg_health: 0, avg_energy: 0 },
	/** @type {Array<any>} */
	events: [],
	connected: false,
	colony_stats: null,
	factions: {}
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

				// Normalize factions array → Record for frontend consumption
				let factions = data.factions ?? state.factions;
				if (Array.isArray(factions)) {
					/** @type {Record<string, any>} */
					const record = {};
					for (const f of factions) {
						if (f.id) record[f.id] = f;
					}
					factions = record;
				}

				return {
					...state,
					tick: data.tick ?? state.tick,
					agents: data.agents ?? state.agents,
					tiles: data.tiles ?? state.tiles,
					metrics: data.metrics ?? state.metrics,
					events: trimmed,
					colony_stats: data.colony_stats ?? state.colony_stats,
					factions
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
