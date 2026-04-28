import { simulationStore } from '../stores/simulationStore.svelte.js';
import { configStore } from '../stores/configStore.svelte.js';
import { get } from 'svelte/store';

/** @type {WebSocket | null} */
let ws = null;
/** @type {ReturnType<typeof setTimeout> | null} */
let reconnectTimer = null;

export function connect() {
  if (ws?.readyState === WebSocket.OPEN) return;

  const url = /** @type {string} */ (get(configStore).wsUrl);
  ws = new WebSocket(url);

  ws.onopen = () => {
    simulationStore.setConnected(true);
    console.log('[WS] Connected to', url);
  };

  /** @param {MessageEvent} event */
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'snapshot') {
        simulationStore.updateFromSnapshot(data.payload);
      }
    } catch (e) {
      console.error('[WS] Parse error:', e);
    }
  };

  ws.onclose = () => {
    simulationStore.setConnected(false);
    ws = null;
    // Auto-reconnect after 3s
    reconnectTimer = setTimeout(connect, 3000);
  };

  /** @param {Event} err */
  ws.onerror = (err) => {
    console.error('[WS] Error:', err);
    ws?.close();
  };
}

export function disconnect() {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  ws?.close();
  ws = null;
}

/** @param {any} data */
export function send(data) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

export function isConnected() {
  return ws?.readyState === WebSocket.OPEN;
}
