import { writable } from 'svelte/store';

/** @typedef {{ tick: number, agents: Record<string, any>, metrics: { population: number, avg_hunger: number, avg_thirst: number, avg_health: number, avg_energy: number }, events: Array<{ event_id: string, type: string, severity: string, description: string, tick: number }>, connected: boolean }} SimulationState */

const INITIAL_STATE = {
  tick: 0,
  agents: {},
  metrics: { population: 0, avg_hunger: 0, avg_thirst: 0, avg_health: 0, avg_energy: 0 },
  events: [],
  connected: false,
};

function createSimulationStore() {
  const { subscribe, set, update } = writable({ ...INITIAL_STATE });

  return {
    subscribe,
    /** @param {any} data */
    updateFromSnapshot(data) {
      update(state => ({
        ...state,
        tick: data.tick ?? state.tick,
        agents: data.agents ?? state.agents,
        metrics: data.metrics ?? state.metrics,
        events: data.events ?? state.events,
      }));
    },
    /** @param {boolean} connected */
    setConnected(connected) {
      update(state => ({ ...state, connected }));
    },
    reset() {
      set({ ...INITIAL_STATE });
    },
  };
}

export const simulationStore = createSimulationStore();
