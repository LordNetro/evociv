# Proposal: Project Skeleton

## Intent

The project exists as design docs and an empty README — no runnable code. This change scaffolds the full monorepo structure: SvelteKit frontend with canvas skeleton and Chart.js, FastAPI backend with WebSocket + SQLAlchemy, monorepo orchestration, and CI.

## Scope

### In Scope
- SvelteKit scaffold (TypeScript, ESLint, Prettier)
- Canvas engine dir: `engine.ts`, `grid.ts`, `entities.ts`, `animation.ts`, `camera.ts` — skeleton only
- State stores as `.svelte.js` rune files: `simulationStore`, `uiStore`, `configStore`
- Chart.js v4 live metric chart component (basic)
- FastAPI project: `app/core/`, `app/models/`, `app/api/`, `app/db/`, `app/simulation/`, `app/ai/`
- `ConnectionManager` WebSocket broadcast pattern
- SQLAlchemy async + aiosqlite models: `sim_events`, `tick_metrics`, `world_configs`
- Root `package.json` with npm workspaces + concurrently
- `requirements.txt` with all pip deps
- CI workflow: `.github/workflows/ci.yml`

### Out of Scope
- Agent logic (FSM, actions, event-driven triggers)
- LLM integration (LiteLLM dep listed, no usage)
- ChromaDB (deferred)
- Simulation tick loop (skeleton file only)
- World grid rendering (skeleton file only)
- Any simulation logic
- Tests (minimal — only enough for CI to pass)

## Capabilities

### New Capabilities
None — project skeleton has no spec-level behavior.

### Modified Capabilities
None — no existing specs to modify.

## Approach

1. **Frontend**: `npx sv create frontend` → add canvas dir and stores
2. **Backend**: Manual scaffolding — `mkdir -p` + empty `__init__.py` + skeleton modules
3. **Root**: `package.json` with npm workspaces + concurrently scripts
4. **WebSocket**: `ConnectionManager` class (connect/disconnect/broadcast)
5. **DB**: SQLAlchemy models mapping the schema from `docs/contracts.md`
6. **CI**: Parallel jobs — ruff lint, svelte-check, pytest (smoke)

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `frontend/` | New | SvelteKit app (scaffold + canvas + stores + charts) |
| `backend/` | New | FastAPI app (core, models, api, db, simulation, ai) |
| `configs/` | New | Example world config dir |
| `package.json` | New | Root monorepo orchestration |
| `.github/workflows/ci.yml` | New | CI pipeline |
| `requirements.txt` | New | Python dependencies |
| `.gitignore` | Existing | Already has needed ignores |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Svelte 5 runes API × Chart.js compat | Low | Test basic chart render post-scaffold |
| FastAPI + WS async error handling | Med | ConnectionManager with try/except per client |
| Zero test coverage at this stage | Low | Smoke test (app starts) is enough for CI |

## Rollback Plan

- Frontend: delete `frontend/` dir
- Backend: delete `backend/` dir
- Root: revert `package.json`, delete `.github/workflows/ci.yml`
- Full revert: `git reset --hard HEAD` (no commits at this point)

## Dependencies

- **npm**: svelte, @sveltejs/kit, @sveltejs/adapter-auto, typescript, eslint, prettier, chart.js, concurrently
- **pip**: fastapi, uvicorn[standard], websockets, sqlalchemy[asyncio], aiosqlite, pydantic, python-dotenv, httpx, pytest, pytest-asyncio, ruff, litellm

## Success Criteria

- [ ] `npm run dev` starts frontend on `:5173` without errors
- [ ] `uvicorn backend.app.main:app` starts backend on `:8000` without errors
- [ ] `npm run dev:all` (concurrently) starts both without errors
- [ ] CI passes: ruff lint, svelte-check, pytest smoke
