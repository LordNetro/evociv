# Tasks: Project Skeleton

## Phase 1: Foundation

- [x] 1.1 T1 — Scaffold SvelteKit frontend with TS+ESLint+Prettier — `frontend/` (npx sv create) — R1 — M
- [x] 1.2 T2 — Root package.json with npm workspaces + concurrently scripts — `package.json` — deps: T1 — R8 — S
- [x] 1.3 T3 — Backend subpackage scaffold with `__init__.py` stubs — `backend/app/{core,models,simulation,ai,api,db}/` — R5 — M
- [x] 1.4 T4 — requirements.txt with all pip deps — `backend/requirements.txt` — deps: T3 — R9 — S

## Phase 2: Backend Core

- [x] 2.1 T5 — pydantic-settings Settings class — `backend/app/core/config.py` — deps: T3 — R5 — S
- [x] 2.2 T6 — Async SQLAlchemy engine, session factory, 4 ORM models (SimEvent, TickMetric, WorldConfig, AgentMemory) — `backend/app/db/{database.py,models.py}` — deps: T4 — R7 — M
- [x] 2.3 T7 — Pydantic schemas for WebSocket messages (ServerMessage, ClientMessage, WorldSnapshot, etc.) — `backend/app/models/schemas.py` — deps: T3 — R6 — M
- [x] 2.4 T8 — ConnectionManager class (connect/disconnect/broadcast) + websocket_endpoint — `backend/app/api/ws.py` — deps: T7 — R6 — M
- [x] 2.5 T9 — FastAPI app with lifespan (startup/shutdown, DB init, WS mount) — `backend/app/main.py` — deps: T5, T6, T8 — R5 — S

## Phase 3: Frontend Core

- [x] 3.1 T10 — 5 canvas engine skeleton classes (Engine, Grid, Entities, Camera, lerp/animation utils) — `frontend/src/lib/canvas/*.ts` — deps: T1 — R2 — M
- [x] 3.2 T11 — 3 Svelte 5 rune stores: simulationStore, uiStore, configStore — `frontend/src/lib/stores/*.svelte.js` — deps: T1 — R3 — M
- [x] 3.3 T12 — Canvas.svelte (Engine mount), MetricChart.svelte (Chart.js + $effect), HUD.svelte — `frontend/src/lib/components/` — deps: T10, T11 — R4 — M

## Phase 4: Testing & CI

- [x] 4.1 T13 — Example world config stubs — `configs/example-world-01/{world.json,agents.yaml,rules.yaml}` — S
- [x] 4.2 T14 — CI workflow: 3 parallel jobs (ruff check, svelte-check, pytest) — `.github/workflows/ci.yml` — deps: T2, T4, T9, T12 — R10 — M
- [x] 4.3 T15 — Backend pytest tests: schema validation, WS broadcast, DB create_all, app import smoke — `backend/tests/` — deps: T6, T7, T8, T9 — R10 — M
