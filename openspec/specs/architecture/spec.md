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

### R2: Canvas 2D Rendering Layer

The system MUST provide a 2D canvas rendering layer under `frontend/src/lib/canvas2d/` using PixiJS v8 with `pixi-viewport` for camera control. A `Canvas2D.svelte` component MUST mount the canvas and manage lifecycle. A `canvas2dStore.ts` MUST bridge simulation state to PixiJS objects.
(Previously: Five skeleton TypeScript files under `frontend/src/lib/canvas/` with skeleton classes for Engine, Grid, Entities, Animation, Camera.)

#### Scenario: Canvas2D mounts PixiJS
- GIVEN `Canvas2D.svelte` is rendered in a route
- WHEN the component mounts
- THEN a PixiJS `Application` initializes on a `<canvas>` element
- AND pixi-viewport is configured for pan/zoom

#### Scenario: Store bridges state
- GIVEN simulation produces new entity positions each tick
- WHEN `canvas2dStore` receives the tick data
- THEN PixiJS sprite positions update via Ticker interpolation

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

---

## Simulation Engine

Extends the core architecture with a data-driven simulation engine: configurable decay rates, FSM-driven agent behavior with role prioritization, 20 ActionTypes with registered handlers, combat interruption, and structure-aware pathfinding.

### Requirements

#### R11 — Decay Rate Constants

The simulation SHALL use these decay rate constants:
- `HUNGER_DECAY`: 0.04 per tick (reduced from 0.1)
- `THIRST_DECAY`: 0.06 per tick (reduced from 0.15)
- `ENERGY_DECAY`: 0.03 per tick (reduced from 0.05)

These slower rates give agents more breathing room for non-survival activities.

##### Scenario: Slower decay gives agents breathing room
- GIVEN an agent with baseline stats
- WHEN 10 ticks pass
- THEN hunger increased by ~0.4 (was 1.0), thirst by ~0.6 (was 1.5), energy decremented by ~0.3 (was 0.5)

#### R12 — Role-Driven FSM Evaluation

The FSM `_fsm_evaluate` method SHALL consult the agent's role priority table when determining action ordering. Role priorities override the hardcoded priority chain. If the role has no entry for a given condition, the FSM falls back to the default chain.

##### Scenario: Role-based action prioritization
- GIVEN a `fighter` agent with hunger=50 and a valid ATTACK target nearby, and a `gatherer` agent with same stats
- WHEN both agents' FSM evaluates
- THEN the fighter prioritizes ATTACK (role top priority), while the gatherer prioritizes GATHER (default chain)

##### Scenario: Role fallback to default chain
- GIVEN an agent role whose priority table does not list a condition (e.g., no ATTACK entry)
- WHEN the FSM evaluates that condition
- THEN the FSM uses the default hardcoded chain for that condition

#### R13 — New Actions in FSM Paths

The FSM SHALL support 20 ActionTypes in its evaluate/moving/executing paths: MOVE, CHOP, DRINK, EAT, GATHER, REST, REPRODUCE, TRADE, SOCIALIZE, FEED_CHILD, MINE, HUNT, FISH, FARM, CRAFT, BUILD, ATTACK, GUARD, EXPLORE, HEAL. Each new action SHALL have entries in `get_action_duration()`, `ACTION_EMOJIS`, and `REGISTRY`.

##### Scenario: New action registered and executed
- GIVEN a `miner` agent adjacent to an iron tile
- WHEN the FSM evaluates and selects MINE per role priorities
- THEN the agent transitions through executing with action_type=MINE and completes the action

#### R14 — Combat Interruption

When an agent takes damage (health reduced by any source), the agent's FSM SHALL be interrupted. If in `idle`, `moving`, or `executing` states, the FSM transitions to `evaluate` on the next tick so the agent can react.

##### Scenario: FSM interruption on damage
- GIVEN an agent in `executing` state gathering resources
- WHEN the agent takes 5 combat damage
- THEN on the next tick, the agent's FSM is forced to `evaluate` state

#### R15 — Structure-Aware Pathfinding

The `is_passable` check SHALL treat tiles occupied by wall-type structures as impassable. Other structure types (storage_hut, house, forge, farm) remain passable.

##### Scenario: Wall blocks pathfinding
- GIVEN a wall structure at (10,10)
- WHEN `world.is_passable(10,10)` is called
- THEN it returns False

#### R16 — FSM Transitions

The FSM SHALL have 6 states via `match/case`: IDLE, MOVING, EXECUTING, EVALUATE, LLM_TRIGGER, LLM_WAITING. One handler method per state. Instinct fallback (find nearest food/water/action per role priorities) when no LLM response. Transitions follow: IDLE→EVALUATE→MOVING/LLM_TRIGGER→LLM_WAITING→IDLE or →MOVING→EXECUTING→EVALUATE.

##### Scenario: Role-aware instinct behavior
- GIVEN a `fighter` agent in LLM_WAITING with low energy and a hostile target adjacent
- WHEN instinct fallback triggers
- THEN the fighter MAY ATTACK the hostile target instead of only seeking food/water

#### R17 — Action Durations

`get_action_duration()` SHALL include entries for all 20 ActionTypes. New entries include: MINE `max(2, 8-strength/10)`, HUNT `max(2, 10-speed/10)`, FISH 5, FARM 5, CRAFT (recipe.duration modified by tool/station), BUILD 10, ATTACK 3, GUARD 3, EXPLORE `max(3, 12-speed/10)`, HEAL 5.

##### Scenario: New action durations computed
- GIVEN an agent with strength=60
- WHEN `get_action_duration(MINE, agent)` is called
- THEN duration = max(2, 8 - 60/10) = max(2, 2) = 2 ticks

#### R18 — Skill and Status Effect Engine Integration

The tick loop (`_tick()`) MUST call `StatusEffectManager.process_tick(agent)` for each agent after `_process_needs()` (step 1) and before FSM execution (step 2). The `_fsm_executing()` post-completion hook MUST call `SkillManager.award_xp(agent, action_type)` after the action handler completes with `success=True`. The `_fsm_llm_waiting()` MUST check the poison fallback condition — if the agent has `"poisoned"` active AND `health < 50`, the agent MUST override the LLM plan and transition to executing REST or HEAL.

(Previously: no skill or status effect processing existed in the engine loop.)

##### Scenario: Tick order preserved
- GIVEN the tick loop at step 1.5
- WHEN _tick() runs
- THEN status effects are processed AFTER need decays but BEFORE FSM execution

##### Scenario: XP awarded on action completion
- GIVEN an agent completing a CHOP action in _fsm_executing()
- WHEN the handler returns success=True
- THEN SkillManager.award_xp(agent, ActionType.CHOP) is called before advancing the plan

#### R19 — Emotion Engine Integration

The tick loop (`_tick()`) MUST call `EmotionManager.process_tick(agent, tick)` for each agent after `StatusEffectManager.process_tick()` (step 1.5) and before FSM execution (step 2). Action completion in `_fsm_executing()` MUST trigger emotion events: `on_skill_up` after XP award, `on_eat` after EAT, `on_rest` after REST, `on_build_complete` after BUILD, `on_win_combat` and `on_lose_combat` after ATTACK that kills target. Resource discovery MUST trigger `on_discovery`. Socialization MUST trigger `on_socialize` (in conversation manager). Emotion modifiers compose multiplicatively with skill and status effect modifiers in `get_action_duration()` and combat damage calculations.

(Previously: no emotion processing existed in the engine loop.)

##### Scenario: Emotion tick runs in correct order
- GIVEN the simulation tick loop processing agents
- WHEN the tick executes
- THEN `StatusEffectManager.process_tick()` runs first, THEN `EmotionManager.process_tick()` for each agent, THEN FSM execution begins

##### Scenario: Combat action triggers emotion
- GIVEN an agent completing an ATTACK action against a hostile target
- WHEN the action handler kills the target
- THEN `EmotionManager.apply_trigger(agent, "on_win_combat")` is called

##### Scenario: Eat action triggers emotion
- GIVEN an agent completing an EAT action successfully
- WHEN the action completes
- THEN `EmotionManager.apply_trigger(agent, "on_eat")` is called
