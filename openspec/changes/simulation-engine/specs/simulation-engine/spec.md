# Simulation Engine Specification

## Purpose

Core simulation runtime: world grid with resource generation, agent FSM with 6 states, action system, BFS pathfinding, event queue, snapshot builder, mock LLM orchestrator, and tick-loop orchestration at 10 ticks/sec. Integrates with FastAPI lifespan, broadcasts state via WebSocket, and logs events/metrics to SQLite.

## Requirements

| # | Requirement | Strength |
|---|-------------|----------|
| **R1** | Async tick loop at configurable rate (default 10/s) with measured-sleep `max(0, tick_interval - elapsed)`. Expose `run()`, `pause()`, `resume()`, `stop()` using `asyncio.Event` for pause/resume and task cancellation for stop. | MUST |
| **R2** | World grid: 50×50 `list[list[Tile]]` each with `resource_type: str \| None` and `amount: int`. Resource generation places trees, water, berries, stone at random positions with configurable density. Float agent coordinates truncated to `int` for grid access. | MUST |
| **R3** | Agent Python dataclass: `id` (str), `name` (str), `position` (tuple[float,float]), `hungher`/`thirst`/`energy`/`health` (float 0-100), `inventory` (dict[str,int]), FSM state, active plan reference, `current_action`, `current_action_emoji`, `action_progress`. Stats clamped to [0, 100] on update. | MUST |
| **R4** | FSM with 6 states via `match/case`: IDLE, MOVING, EXECUTING, EVALUATE, LLM_TRIGGER, LLM_WAITING. One handler method per state. Instinct fallback (find nearest food/water) when no LLM response. Transitions follow the diagram: IDLE→EVALUATE→MOVING/LLM_TRIGGER→LLM_WAITING→IDLE or →MOVING→EXECUTING→EVALUATE. | MUST |
| **R5** | Action system: `ActionType` enum (MOVE, CHOP, DRINK, EAT, GATHER, REST) + `REGISTRY` dict `dict[ActionType, Callable[[Agent, PlanStep, World], ActionResult]]`. Handlers mutate agent state and/or inventory. BUILD and ATTACK MAY be stubs. | MUST |
| **R6** | BFS pathfinding returning `list[tuple[int,int]]` waypoints. All resource tiles treated as passable. Grid boundaries are impassable. Returns empty list for unreachable targets. | MUST |
| **R7** | Event queue: per-tick accumulation of proximity-based encounter events via O(n²) pairwise distance check. Events drained each tick and included in snapshot. | MUST |
| **R8** | WorldSnapshot builder producing Pydantic `WorldSnapshot` with delta tracking: dirty tiles (only changed tiles), dirty agents, removed_agents list, drained events. Metrics compiled as `SimulationMetrics` each tick. | MUST |
| **R9** | MockLLMOrchestrator: returns hardcoded JSON plans matching LLMPlan schema, 0.5-2s simulated async latency, 90% success rate (10% return invalid plan for testing). | MUST |
| **R10** | FastAPI lifespan: create engine singleton on startup, call `run()`; on shutdown, call `stop()` and cancel the tick task. Engine MUST NOT block shutdown beyond 2s. | MUST |
| **R11** | Broadcast: per tick, build `ServerMessage(type="snapshot", payload=snapshot.dict())` and pass to `ConnectionManager.broadcast()`. | MUST |
| **R12** | SQLite logging: each tick, write SimEvent rows for drained events and one TickMetric row. Uses `async with async_session_maker()` — MUST be async and MUST NOT block the tick loop. Failures MUST NOT crash the engine (log and continue). | MUST |
| **R13** | Tests: engine lifecycle (start/pause/resume/stop), agent lifecycle (spawn→move→act→complete), all action types, FSM transitions (each of 6 states), snapshot building (full + delta), mock LLM response handling. | MUST |

## Scenarios

### Tick Loop (R1)
- GIVEN engine with `tick_rate=0.1` WHEN `run()` starts THEN ~10 ticks complete per second
- GIVEN running engine WHEN `pause()` THEN ticks stop; WHEN `resume()` THEN ticks resume
- GIVEN running engine WHEN `stop()` THEN loop exits with no further ticks
- GIVEN tick processing takes 40ms WHEN sleep calculates THEN `sleep = max(0, 0.1 - 0.04) = 0.06s`

### World Grid (R2)
- GIVEN generated world WHEN inspected THEN grid has 50 rows × 50 cols
- GIVEN agent at (24.7, 13.2) WHEN accessing tile THEN uses `grid[13][24]` (int-truncated)

### Agent (R3)
- GIVEN default Agent() WHEN created THEN hunger=thirst=energy=health=100, inventory={}
- GIVEN stat update results in value > 100 or < 0 WHEN applied THEN clamped to [0, 100]

### FSM (R4)
- GIVEN agent in IDLE with valid plan WHEN FSM runs THEN transitions through MOVING→EXECUTING→EVALUATE→IDLE
- GIVEN agent in IDLE with no plan and no critical need WHEN FSM runs THEN EVALUATE→instinct (find nearest food/water)
- GIVEN agent in LLM_WAITING WHEN FSM runs THEN instinct behavior continues (non-blocking)
- GIVEN agent in MOVING with critical need (< 15%) WHEN FSM runs THEN aborts current plan → EVALUATE

### Actions (R5)
- GIVEN agent thirst=30 adjacent to water WHEN DRINK handler executes THEN thirst=100
- GIVEN agent adjacent to tree tile WHEN CHOP handler executes THEN inventory.wood increases
- GIVEN agent energy < 20 WHEN REST handler executes THEN energy=100
- GIVEN BUILD or ATTACK handler invoked WHEN not yet implemented THEN returns ActionResult with success=False

### Pathfinding (R6)
- GIVEN start=(0,0) target=(3,0) with all passable WHEN BFS THEN returns [(1,0),(2,0),(3,0)]
- GIVEN target=(-1,-1) WHEN BFS THEN returns empty list
- GIVEN start=(0,0) target=(49,49) open terrain WHEN BFS THEN returns path traversing full grid

### Event Queue (R7)
- GIVEN two agents within interaction radius (3 tiles) WHEN tick processes queue THEN encounter Event produced
- GIVEN events accumulated WHEN tick completes THEN queue is drained, all events in snapshot

### Snapshot Builder (R8)
- GIVEN tick 0 initial state WHEN snapshots built THEN agents contains all agents, tiles contains all non-empty tiles
- GIVEN no tile changes since last snapshot WHEN delta built THEN tiles=[]
- GIVEN agent with health ≤ 0 WHEN snapped built THEN agent in removed_agents, absent from agents

### Mock LLM (R9)
- GIVEN MockLLMOrchestrator WHEN `request_plan(state)` called THEN returns valid plan after simulated delay (0.5-2s)
- GIVEN 100 calls to MockLLM WHEN aggregated THEN ~10% (8-12) return simulated-failure responses

### Lifespan (R10)
- GIVEN FastAPI starts WHEN lifespan startup fires THEN engine begins ticking
- GIVEN running engine WHEN FastAPI shutdown fires THEN engine loop exits, tick task cancelled within 2s

### Broadcast (R11)
- GIVEN running engine with 2 connected WS clients WHEN tick completes THEN both clients receive snapshot via `manager.broadcast`
- GIVEN running engine with 0 connected clients WHEN tick completes THEN broadcast is a no-op (no error)

### SQLite Logging (R12)
- GIVEN a tick with 3 events WHEN tick completes THEN 3 rows inserted into sim_events table
- GIVEN a tick with 5 agents WHEN tick completes THEN 1 row in tick_metrics with population=5
- GIVEN DB write fails (e.g. connection error) WHEN logging runs THEN engine continues, error logged

### Tests (R13)
- GIVEN engine test fixture WHEN `start → pause → resume → stop` exercised THEN no exceptions, tick count matches elapsed time
- GIVEN agent with multi-step plan WHEN FSM processes sufficient ticks THEN plan completes, agent returns to IDLE
- GIVEN one dirty agent after tick N WHEN building snapshot for tick N+1 THEN agents dict contains exactly that one agent
- GIVEN each ActionType handler WHEN invoked with valid inputs THEN returns ActionResult with success=True and correct stat mutations
- GIVEN FSM transition for each of 6 states WHEN triggered by appropriate condition THEN current_state reflects the target state
