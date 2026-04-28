# Design: Project Skeleton

## Technical Approach

Scaffold a running monorepo with zero simulation logic: SvelteKit frontend (canvas engine skeleton + Chart.js chart + rune-based stores) and FastAPI backend (WebSocket ConnectionManager + SQLAlchemy async models + config + Pydantic schemas). Root npm workspaces + concurrently for orchestration. CI with three parallel jobs.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Svelte 5 runes vs traditional `writable` stores | Runes require `.svelte.js` extension; writable stores have broader ecosystem | **Runes** — runes are the Svelte 5 idiomatic path and this is a greenfield project |
| Chart.js v4 directly vs layer wrapper | Direct = simpler, wrapper = testable mock | **Direct** — skeleton phase; no testing depth needed yet |
| WebSocket in `app/api/ws.py` vs separate package | Single file is simpler for < 200 LOC | **Single module** — ConnectionManager + endpoint in one file |
| SQLAlchemy async vs sync | Async = compatible with FastAPI lifecycle, sync = simpler setup | **Async (aiosqlite)** — FastAPI is async-native; switching later is costly |
| 3 vs 4 DB models | Spec (R7) mentions 3; contracts.md defines 4 including `agent_memories` | **4 models** — follow contracts.md as established architecture truth |
| npm workspaces vs Turborepo | Turborepo adds caching/complexity; workspaces are zero-config | **npm workspaces** — sufficient for two packages |

## Component Tree

```
App.svelte
├── Canvas.svelte           — mounts <canvas>, instantiates Engine
│   └── canvas/engine.ts    — rAF loop → Grid + Entities + Camera
├── HUD.svelte              — right sidebar container
│   ├── AgentInspector      — selected agent details (reads uiStore)
│   ├── MetricChart         — Chart.js line chart (reads simulationStore.metrics)
│   └── EventLog            — scrolling event list (reads simulationStore.events)
└── Controls.svelte         — pause/resume/speed (writes configStore)
```

All components read from stores; stores read from WebSocket. No prop drilling.

## Data Flow

```
Server tick → ConnectionManager.broadcast(snapshot)
  → WS JSON text
  → frontend ws.ts (raw socket)
    → simulationStore.update(snapshot)   [writes $state]
      → $effect in Canvas.svelte → engine.render()
      → $effect in MetricChart → chart.update()
      → $derived in HUD panels → reactive re-render
    → uiStore.selectedEntityId           [reads from click events]
    → configStore.tickRate               [writes from Controls → ws.send]
```

## Module Responsibilities

### Frontend

| Module | Public API | Dependencies | State Owned |
|--------|-----------|--------------|-------------|
| `canvas/engine.ts` | `Engine { start, stop, resize, onSnapshot }` | grid, entities, animation, camera | rAF id, canvas ref, camera state |
| `canvas/grid.ts` | `Grid { render(ctx, tiles) }` | none (pure render) | texture cache |
| `canvas/entities.ts` | `Entities { render(ctx, agents) }` | animation (lerp) | per-agent interpolated positions |
| `canvas/animation.ts` | `lerp, easeInOut, smoothstep` | none (pure functions) | none |
| `canvas/camera.ts` | `Camera { getTransform(), pan(dx,dy), zoom(factor) }` | none | offsetX, offsetY, scale |
| `stores/simulationStore.svelte.js` | `createSimulationStore()` returns `{ tick, entities, metrics, events, wsConnected, update }` | ws client | $state: tick, entities, metrics |
| `stores/uiStore.svelte.js` | `createUiStore()` returns `{ selectedEntityId, sidebarOpen, viewMode }` | none | $state: selection, panels |
| `stores/configStore.svelte.js` | `createConfigStore()` returns `{ tickRate, worldSeed, computed }` | none | $state: config, $derived |

### Backend

| Module | Public API | Dependencies | State Owned |
|--------|-----------|--------------|-------------|
| `app/core/config.py` | `Settings` (pydantic-settings) | none | env-derived tick_rate, db_path |
| `app/api/ws.py` | `ConnectionManager { connect, disconnect, broadcast }`, `websocket_endpoint` | schemas | set of active WS connections |
| `app/models/schemas.py` | `ServerMessage`, `ClientMessage`, `WorldSnapshot`, `AgentState`, `SimulationMetrics`, `TileUpdate`, `SimEvent` (all Pydantic) | none | none |
| `app/db/models.py` | `SimEvent`, `TickMetric`, `WorldConfig`, `AgentMemory` (SQLAlchemy) | database (Base) | none (ORM) |
| `app/db/database.py` | `engine`, `async_session` | aiosqlite | SQLAlchemy engine, sessionmaker |
| `app/main.py` | `app` (FastAPI) | config, ws, database | lifespan state (startup/shutdown) |

## Database Design

```
SimEvent                TickMetric              WorldConfig             AgentMemory
├── id (PK, int)        ├── id (PK, int)        ├── id (PK, int)        ├── id (PK, int)
├── tick (int, idx)     ├── tick (int, UNIQUE)  ├── name (str, UNIQUE)  ├── agent_id (str, idx)
├── agent_id (str,idx)  ├── population (int)    ├── config (JSON)       ├── chroma_id (str, UNIQUE)
├── event_type (str)    ├── avg_hunger (float)  ├── active (bool)       ├── timestamp (int)
├── description (str)   ├── avg_thirst (float)  ├── created_at (dt)     ├── memory_type (str)
├── metadata (JSON)     ├── avg_health (float)  └── updated_at (dt)     └── summary (str)
└── created_at (dt)     ├── avg_energy (float)
                        ├── total_wood (int)        No foreign keys.
                        ├── total_food (int)        All models standalone —
                        ├── total_stone (int)       independent event sourcing.
                        ├── total_buildings (int)
                        ├── deaths_this_tick (int)
                        └── births_this_tick (int)
```

## WebSocket Protocol Flow

```
Client (browser)               Server (FastAPI)
       │                            │
       │──── connect /ws ──────────>│  ws.py: manager.connect(ws)
       │<── accept (101) ──────────│  endpoint calls ws.accept()
       │                            │
       │                            │  [future: simulation tick loop]
       │                            │  broadcast(snapshot) via manager
       │<── {"type":"snapshot",     │
       │     "payload":{...}} ──────│
       │                            │
       │  simulationStore           │
       │  .update(payload)          │
       │  → canvas.render()         │
       │  → chart.update()          │
       │                            │
       │── {"type":"command",       │
       │     "payload":             │
       │     {"command":"pause"}} ──>│  parse + route (future: sim engine)
       │<── {"type":"config_ack"} ──│  manager.broadcast(ack)
       │                            │
       │── disconnect ────────────>│  manager.disconnect(ws)
```

## Key Interfaces

```typescript
// canvas/engine.ts
export class Engine {
  constructor(canvas: HTMLCanvasElement);
  start(): Promise<void>;
  stop(): void;
  resize(w: number, h: number): void;
  onSnapshot(snapshot: WorldSnapshot): void;
}

// stores/simulationStore.svelte.js
export function createSimulationStore(): {
  get tick(): number;
  get entities(): Map<string, AgentState>;
  get metrics(): SimulationMetrics | null;
  get events(): SimEvent[];
  get wsConnected(): boolean;
  update(snapshot: WorldSnapshot): void;
};

// stores/uiStore.svelte.js
export function createUiStore(): {
  get selectedEntityId(): string | null;
  get sidebarOpen(): boolean;
  get viewMode(): 'canvas' | 'charts' | 'split';
  toggleSidebar(): void;
  selectEntity(id: string | null): void;
};

// stores/configStore.svelte.js
export function createConfigStore(): {
  get tickRate(): number;
  get worldSeed(): string | null;
  get effectiveTickRate(): number;   // $derived
  update(config: Partial<ConfigState>): void;
};
```

```python
# app/models/schemas.py
from pydantic import BaseModel
from typing import Literal

class ServerMessage(BaseModel):
    type: Literal["snapshot", "llm_response", "error", "config_ack"]
    payload: dict

class ClientMessage(BaseModel):
    type: Literal["command", "config_change", "agent_edit"]
    payload: dict

class TileUpdate(BaseModel):
    x: int; y: int
    resource_type: str | None; amount: float

class AgentState(BaseModel):
    id: str; name: str; position: tuple[float, float]; role: str
    hunger: float; thirst: float; energy: float; health: float
    current_state: str; current_action: str | None; action_progress: float
    inventory: dict[str, int]

class SimulationMetrics(BaseModel):
    population: int; avg_hunger: float; avg_thirst: float
    avg_health: float; avg_energy: float; total_wood: int
    total_food: int; total_stone: int; total_buildings: int
    deaths_this_tick: int; births_this_tick: int; tick_rate: float

class SimEvent(BaseModel):
    event_id: str; type: str; severity: Literal["info", "warning", "critical"]
    description: str; agent_ids: list[str]; position: tuple | None; tick: int

class WorldSnapshot(BaseModel):
    tick: int; timestamp: int
    tiles: list[TileUpdate]
    agents: dict[str, AgentState]
    removed_agents: list[str]
    metrics: SimulationMetrics
    events: list[SimEvent]
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `frontend/` | Create | SvelteKit scaffold (package.json, svelte.config.js, tsconfig.json, src/) |
| `frontend/src/lib/canvas/engine.ts` | Create | Engine class: rAF loop, orchestrator |
| `frontend/src/lib/canvas/grid.ts` | Create | Grid class: tile map rendering |
| `frontend/src/lib/canvas/entities.ts` | Create | Entities class: agent circles + interpolation |
| `frontend/src/lib/canvas/animation.ts` | Create | lerp, easing utility functions |
| `frontend/src/lib/canvas/camera.ts` | Create | Camera class: pan + zoom transforms |
| `frontend/src/lib/stores/simulationStore.svelte.js` | Create | Rune-based simulation state |
| `frontend/src/lib/stores/uiStore.svelte.js` | Create | Rune-based UI state |
| `frontend/src/lib/stores/configStore.svelte.js` | Create | Rune-based config state |
| `frontend/src/lib/components/MetricChart.svelte` | Create | Chart.js chart bound via $effect |
| `frontend/src/lib/components/Canvas.svelte` | Create | Canvas mount + Engine lifecycle |
| `frontend/src/lib/components/HUD.svelte` | Create | Sidebar panel container |
| `backend/` | Create | FastAPI scaffold (all subpackages) |
| `backend/app/core/config.py` | Create | pydantic-settings Settings class |
| `backend/app/api/ws.py` | Create | ConnectionManager + ws endpoint |
| `backend/app/models/schemas.py` | Create | Pydantic models for WS messages |
| `backend/app/db/models.py` | Create | 4 SQLAlchemy async ORM models |
| `backend/app/db/database.py` | Create | Engine + async session factory |
| `backend/app/main.py` | Create | FastAPI app factory + lifespan |
| `backend/requirements.txt` | Create | All pip dependencies |
| `package.json` | Create | Root npm workspaces + concurrently scripts |
| `.github/workflows/ci.yml` | Create | 3-job CI pipeline |
| `configs/example-world-01/world.json` | Create | Example world config stub |
| `configs/example-world-01/agents.yaml` | Create | Example agents stub |
| `configs/example-world-01/rules.yaml` | Create | Example rules stub |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (backend) | Pydantic schemas validate correctly | `pytest` — instantiate each model, assert fields |
| Unit (backend) | ConnectionManager connect/disconnect/broadcast | `pytest-asyncio` — mock WS, assert broadcast |
| Unit (backend) | SQLAlchemy models create all tables | `pytest-asyncio` — create_engine, create_all, inspect |
| Smoke (backend) | FastAPI app imports and starts | `pytest` — `from app.main import app`, assert instance |
| Type-check (frontend) | All TS compiles | `svelte-check` |
| Lint | ruff passes on all .py files | `ruff check` |

## Migration / Rollout

No migration required. This is a greenfield scaffold with no existing data.

## Open Questions

- None — all decisions resolved in existing architecture docs and exploration.
