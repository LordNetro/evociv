# Project Skeleton Specification

## Purpose
Scaffold the evociv monorepo from zero: SvelteKit frontend (canvas skeletons + Chart.js), FastAPI backend (WebSocket + SQLAlchemy models), and orchestrating infrastructure (monorepo scripts, CI, dependencies).

## Requirements

### R1: SvelteKit Frontend Scaffold
The system MUST provide a SvelteKit app at `frontend/` with TypeScript, ESLint, and Prettier configured.

**Files**: `frontend/package.json`, `svelte.config.js`, `tsconfig.json`, `.eslintrc.cjs`, `.prettierrc`

#### Scenario: Dev server starts
- GIVEN the frontend is scaffolded with dependencies installed
- WHEN `npm run dev` is executed
- THEN the dev server starts on port 5173 without compilation errors

### R2: Canvas Engine Skeletons
The system MUST provide five skeleton TypeScript files under `frontend/src/lib/canvas/`.

**Files**: `engine.ts`, `grid.ts`, `entities.ts`, `animation.ts`, `camera.ts`
Each MUST export a class matching its domain (e.g., `Camera`, `Grid`) and compile without errors.

#### Scenario: Module imports
- GIVEN all five files exist with skeleton exports
- WHEN imported in a TypeScript module
- THEN compilation succeeds

### R3: Svelte 5 Reactive Stores
Three `.svelte.js` files under `frontend/src/lib/stores/` MUST use Svelte 5 runes:
- `simulationStore.svelte.js`: `$state` for `tick`, `entities`, `metrics`; exports `tick()` function
- `uiStore.svelte.js`: `$state` for `selectedEntity`, `sidebarOpen`, `viewMode`
- `configStore.svelte.js`: `$state` for world config parameters; `$derived` for computed values

#### Scenario: Reactivity
- GIVEN a Svelte 5 component imports a store
- WHEN a `$state` variable is reassigned
- THEN dependent `$derived`/`$effect` blocks re-evaluate

### R4: Chart.js Metric Chart
`frontend/src/lib/components/MetricChart.svelte` MUST render a Chart.js chart bound via `$effect` to a `metrics` prop.

#### Scenario: Chart renders
- GIVEN the component receives a `metrics: number[]` prop
- WHEN mounted
- THEN a Chart.js canvas renders and updates when data changes

### R5: FastAPI Application Structure
The backend at `backend/` MUST contain six subpackages, each with `__init__.py`: `app/core/`, `app/models/`, `app/api/`, `app/db/`, `app/simulation/`, `app/ai/`. `app/main.py` MUST export a `FastAPI` instance.

#### Scenario: Import succeeds
- GIVEN the backend directory tree exists
- WHEN running `from app.main import app`
- THEN the FastAPI instance is created without import errors

### R6: ConnectionManager WebSocket
`app/api/ws.py` MUST export a `ConnectionManager` class with:
- `connect(ws)`: accept and track a WebSocket connection
- `disconnect(ws)`: remove and cleanup
- `broadcast(data: dict)`: send JSON to all clients, catching per-client exceptions

#### Scenario: Broadcast to multiple clients
- GIVEN two connected WebSocket clients
- WHEN `manager.broadcast({"tick": 1})` is called
- THEN both clients receive the JSON message

#### Scenario: Partial failure tolerance
- GIVEN one active and one stale WebSocket client
- WHEN broadcast is called
- THEN the active client still receives the message without error

### R7: SQLAlchemy Async Models
`app/db/models.py` MUST define three async SQLAlchemy models using `aiosqlite`:
1. `SimEvent`: `id` (PK), `tick` (int), `event_type` (str), `agent_id` (str), `data` (JSON), `timestamp` (datetime)
2. `TickMetric`: `id` (PK), `tick` (int), `metric_name` (str), `metric_value` (float)
3. `WorldConfig`: `id` (PK), `key` (str), `value` (str), `updated_at` (datetime)

#### Scenario: Schema creation
- GIVEN an async SQLAlchemy engine with aiosqlite
- WHEN `Base.metadata.create_all` runs
- THEN all three tables exist in the database

### R8: Monorepo Orchestration
Root `package.json` MUST define npm workspaces (`frontend/`) and scripts using `concurrently`:
- `dev:front`: starts SvelteKit dev server
- `dev:backend`: starts uvicorn on port 8000
- `dev:all`: runs both concurrently

#### Scenario: Both services start
- GIVEN frontend deps and Python venv are ready
- WHEN `npm run dev:all` is executed
- THEN frontend runs on :5173 and backend on :8000

### R9: Python Dependencies
`requirements.txt` MUST list: `fastapi`, `uvicorn[standard]`, `websockets`, `sqlalchemy[asyncio]`, `aiosqlite`, `pydantic`, `python-dotenv`, `httpx`, `pytest`, `pytest-asyncio`, `ruff`, `litellm`.

#### Scenario: Installation succeeds
- GIVEN a Python 3.11+ environment
- WHEN `pip install -r requirements.txt` runs
- THEN all packages install without conflicts

### R10: CI Pipeline
`.github/workflows/ci.yml` MUST define three parallel jobs: lint (ruff check), type-check (svelte-check), test (pytest).

#### Scenario: CI passes
- GIVEN a PR is opened against main
- WHEN CI workflow triggers
- THEN all three jobs pass
