# Design: Simulation Engine

## Technical Approach

Six modules in `backend/app/simulation/` implement the tick loop, world grid, agent FSM, action system, event queue, and snapshot builder. Pure Python stdlib — zero new dependencies. Engine wired into FastAPI lifespan via DI of `ConnectionManager` and `async_session_maker`.

## Architecture Decisions

| Decision | Options | Tradeoff | Choice |
|----------|---------|----------|--------|
| FSM pattern | State pattern vs match/case | State pattern = more boilerplate, more extensible. match/case = simpler, direct, fits 6 states. | **match/case in engine.py** — not a separate fsm.py. Keeps transitions visible in one place. |
| Action dispatch | Class-per-action vs REGISTRY dict | Class = testable in isolation, more files. REGISTRY = single lookup, easy to add. | **REGISTRY dict[ActionType, Callable]** — 6 handlers, no OOP overhead. |
| Grid storage | 2D list vs dict[(x,y), Tile] vs spatial hash | dict = sparse, better for large. 2D list = simplest for 50×50 fixed grid. | **list[list[Tile]]** — 2500 cells is trivially small. |
| Pathfinding | BFS vs A* vs Dijkstra | A* = optimal for large grids with obstacles. BFS = simpler, same result on 50×50 uniform grid. | **BFS** — 4-directional, all resource tiles passable. Good enough for 2500 cells. |
| Proximity detection | Spatial hash vs O(n²) | Spatial hash = faster at scale. O(n²) = simpler, adequate for ≤20 agents. | **O(n²) pairwise distance** — filters by sociability threshold. |
| Snapshot delta | Full vs delta per entity type | Full = simple, wasteful. Delta = efficient, more complex. | **Delta for tiles** (dirty set), **full for agents** (always send all). |

## Module Responsibilities

### `engine.py` — `SimulationEngine`
- **Public API**: `SimEngine(world_config, ws_manager, db_session_factory, llm_orchestrator, tick_rate)`, `run()`, `pause()`, `resume()`, `stop()`
- **Dependencies**: `world.py` (World), `agent.py` (AgentState, FSM step), `actions.py` (ActionType, REGISTRY), `event_queue.py` (EventQueue), `snapshot.py` (SnapshotBuilder), `app.api.ws` (ConnectionManager), `app.core.config` (settings), `app.db.database` (async_session_maker)
- **State owned**: Tick counter, `asyncio.Event` for pause, `asyncio.Task` for loop, agents list, world instance, event queue, snapshot builder, dirty tracking sets

### `agent.py` — Agent dataclass + FSM
- **Public API**: `@dataclass Agent(id, name, position, hunger, thirst, energy, health, strength, intelligence, sociability, speed, inventory, current_state, current_action, current_action_emoji, action_progress, active_plan, plan_step_index, llm_call_pending)`, `clamp_stats()`
- **Dependencies**: stdlib only
- **State owned**: Agent mutable state (lives on engine's agents list)

### `actions.py` — Action registry + handlers
- **Public API**: `ActionType(Enum)` (MOVE, CHOP, DRINK, EAT, GATHER, REST, BUILD, ATTACK), `REGISTRY: dict[ActionType, Callable]`, `ActionResult(success, stat_deltas, inventory_deltas, events)`
- **Dependencies**: `agent.py` (Agent), `world.py` (World)
- **State owned**: None (stateless handlers, pure functions)

### `world.py` — World grid + BFS
- **Public API**: `World(width, height, seed?)`, `generate_resources(config)`, `get_tile(x, y)`, `set_tile(x, y, resource_type, amount)`, `bfs(start, target)`, `regenerate_resources()`, `get_nearby_resources(pos, radius)`
- **Dependencies**: stdlib (random)
- **State owned**: `grid: list[list[Tile]]`, `dirty_tiles: set[tuple[int,int]]`

### `event_queue.py` — Proximity encounters
- **Public API**: `EventQueue()`, `process_proximity(agents, world, radius)`, `drain() -> list[SimEvent]`
- **Dependencies**: stdlib (math for distance)
- **State owned**: `_events: list[SimEvent]` (accumulated, drained each tick)

### `snapshot.py` — Snapshot builder
- **Public API**: `SnapshotBuilder()`, `build(tick, agents, world, event_queue, metrics) -> WorldSnapshot`, `mark_tile_dirty(x, y)`, `mark_agent_dirty(agent_id)`, `add_removed_agent(agent_id)`, `reset_delta()`
- **Dependencies**: `app.models.schemas` (WorldSnapshot, AgentState, TileUpdate, SimulationMetrics)
- **State owned**: `dirty_tiles: set`, `dirty_agents: set`, `removed_agents: list`

## Engine Lifecycle

```
FastAPI startup
       │
       ▼
lifespan() ──→ engine = SimEngine(..., ws_manager, ...)
       │
       ├── engine.run() ──→ asyncio.create_task(_tick_loop())
       │                           │
       │                      ┌────▼──────────────────┐
       │                      │  WHILE self._running:  │
       │                      │    tick_start = time() │
       │                      │    await self._pause   │
       │                      │      .wait()           │
       │                      │    await self._tick()  │
       │                      │    elapsed = time() -  │
       │                      │      tick_start        │
       │                      │    sleep = max(0,      │
       │                      │      interval-elapsed) │
       │                      │    await asyncio.sleep(│
       │                      │      sleep)            │
       │                      └────────────────────────┘
       │
       ▼ yield (app is live)
       │
       ▼ shutdown
engine.stop() → self._running = False
                 self._tick_task.cancel()
                 await asyncio.wait_for(task, timeout=2.0)
```

## Per-Tick Data Flow

```
_tick()
  │
  ├─ 1. Update needs
  │     for agent in agents:
  │       agent.hunger += HUNGER_DECAY (≈0.5/tick)
  │       agent.thirst += THIRST_DECAY (≈0.8/tick)
  │       agent.energy -= ENERGY_DECAY (≈0.3/tick)
  │       clamp_stats(agent)
  │       if agent.health ≤ 0 → snapshot.mark_removed(agent.id)
  │
  ├─ 2. Run FSM per agent (match/case)
  │     match agent.current_state:
  │       IDLE → check needs + plan → EVALUATE
  │       EVALUATE → needs_met → IDLE
  │                → has_resource → MOVING (BFS to target)
  │                → needs_llm → LLM_TRIGGER (create Future)
  │       MOVING → advance position
  │              → arrived → EXECUTING
  │              → critical_need → EVALUATE (abort)
  │       EXECUTING → advance action_progress
  │                 → done → more steps → MOVING
  │                 → done → complete → EVALUATE
  │       LLM_TRIGGER → if not pending: create_task(mock_llm)
  │                   → LLM_WAITING
  │       LLM_WAITING → future done → parse → MOVING
  │                   → timeout/fail → instinct → EVALUATE
  │
  ├─ 3. Process event queue
  │     event_queue.process_proximity(agents, world, radius=3)
  │
  ├─ 4. Poll LLM futures
  │     for agent in agents where llm_waiting:
  │       if agent.llm_future.done():
  │         parse response → set plan or fallback
  │
  ├─ 5. Update world
  │     world.regenerate_resources()
  │
  ├─ 6. Compute metrics
  │     avg_hunger, avg_thirst, population, deaths, etc.
  │
  ├─ 7. Build snapshot
  │     snapshot = builder.build(tick, agents, world, event_queue, metrics)
  │
  ├─ 8. Broadcast
  │     msg = ServerMessage(type="snapshot", payload=snapshot.model_dump())
  │     await ws_manager.broadcast(msg)
  │
  └─ 9. Log to SQLite (non-blocking)
        async with async_session_maker() as session:
          session.add_all(SimEvent rows)
          session.add(TickMetric row)
          await session.commit()
        # wrapped in try/except — failures logged, never crash
```

## Key Algorithms

### Measured Sleep
```python
interval = 1.0 / (1.0 / settings.tick_rate)  # 0.1s default
elapsed = time.monotonic() - tick_start
sleep = max(0, interval - elapsed)
await asyncio.sleep(sleep)
```

### BFS Pathfinding
```python
def bfs(start, target, grid):
    if out_of_bounds(target): return []
    queue = deque([start])
    came_from = {start: None}
    while queue:
        current = queue.popleft()
        if current == target: break
        for dx, dy in [(0,1),(1,0),(0,-1),(-1,0)]:
            nx, ny = current[0]+dx, current[1]+dy
            if in_bounds(nx, ny) and (nx,ny) not in came_from:
                came_from[(nx,ny)] = current
                queue.append((nx,ny))
    if target not in came_from: return []
    path = []; cur = target
    while cur is not None: path.append(cur); cur = came_from[cur]
    return list(reversed(path))
```

### Proximity Check
```python
for i, a in enumerate(agents):
    for b in agents[i+1:]:
        d = hypot(a.x-b.x, a.y-b.y)
        if d < 3 and random() < a.sociability/100:
            events.append(encounter_event(a, b))
```

### Delta Tracking
```python
# SnapshotBuilder state per tick:
dirty_tiles: set[tuple[int,int]]      # tiles modified this tick
dirty_agents: set[str]                 # agents whose state changed
removed_agents: list[str]              # agents that died

# On build(): tiles from dirty_tiles only, agents from dirty_agents + all alive
# On reset(): clear all sets after snapshot sent
```

## Integration Points

| Integration | Mechanism | Code |
|-------------|-----------|------|
| ConnectionManager | Constructor DI | `SimEngine(ws_manager=manager)` |
| Settings | Direct import | `from app.core.config import settings` — tick_rate, db url |
| SQLite logging | Constructor DI | `SimEngine(db_session_factory=async_session_maker)` |
| FastAPI lifespan | Create engine + run in startup, stop in shutdown | `main.py` lifespan block |
| LLM Orchestrator | Constructor DI | `SimEngine(llm_orchestrator=MockLLMOrchestrator())` |

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/simulation/engine.py` | Create | SimEngine with tick loop, pause/resume/stop |
| `backend/app/simulation/agent.py` | Create | Agent dataclass, FSM handler methods |
| `backend/app/simulation/actions.py` | Create | ActionType enum, REGISTRY, handlers |
| `backend/app/simulation/world.py` | Create | World grid, resource gen, BFS pathfinding |
| `backend/app/simulation/event_queue.py` | Create | Proximity encounter detection |
| `backend/app/simulation/snapshot.py` | Create | WorldSnapshot builder with delta tracking |
| `backend/app/simulation/__init__.py` | Modify | Export public symbols |
| `backend/app/main.py` | Modify | Add engine lifecycle to lifespan |
| `backend/tests/test_engine.py` | Create | Engine lifecycle + integration tests |

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Action handlers | Call each handler with known state, assert ActionResult |
| Unit | BFS pathfinding | Assert path length and waypoints for known inputs |
| Unit | Snapshot delta | Modify tiles, build snapshot, assert delta content |
| Unit | Agent stats clamping | Push stats beyond [0,100], assert clamped |
| Integration | Engine lifecycle | `start → tick → pause → resume → stop`, count ticks |
| Integration | FSM transitions | Create agent in each state, run FSM step, assert next state |
| Integration | WS broadcast | Mock ConnectionManager, assert broadcast called per tick |
| Integration | SQLite logging | Run N ticks, assert row count in sim_events + tick_metrics |
| Integration | Mock LLM | Call `request_plan()`, assert valid LLMPlan, measure ~1s latency |

## Open Questions

- None resolved. MockLLM from day 1 defers all real-LLM questions.
