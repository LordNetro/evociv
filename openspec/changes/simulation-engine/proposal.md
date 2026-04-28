# Proposal: Simulation Engine

## Intent

The project skeleton exists but does nothing — no simulation runs, no agents exist, no world is generated. This change makes the simulation actually run: agents navigate a resource-rich world, perform survival actions, and broadcast state snapshots over WebSocket.

## Scope

### In Scope
- `SimulationEngine` class with async tick loop (run/pause/resume/stop)
- Agent model (id, position, stats, inventory, FSM state, active plan)
- FSM runner with all 6 states (IDLE → MOVING → EXECUTING → EVALUATE → LLM_TRIGGER → LLM_WAITING)
- Action system (ActionType enum + registry + handlers: move, chop, drink, eat, gather, rest)
- 50×50 world grid with tile-based resource generation (trees, water, berries, stone)
- BFS pathfinding for agent movement
- `WorldSnapshot` builder integrating with existing Pydantic schemas
- Delta tracking for tiles and agents
- Event queue with proximity-based encounters
- `MockLLMOrchestrator` returning hardcoded plans for dev
- FastAPI lifespan integration (start/stop engine)
- ConnectionManager integration (broadcast snapshots)
- Event/metric logging to SQLite via existing models
- Engine tests

### Out of Scope
- Real LLM integration (LiteLLM/orchestrator.py — deferred)
- ChromaDB agent memory (deferred)
- Agent relationships (deferred)
- Building/construction (handler stub only)
- Combat/attack (handler stub only)
- Day/night cycle or weather
- RL — Phase 2

## Capabilities

### New Capabilities
- `simulation-engine`: Core simulation lifecycle, world grid with resource generation, agent FSM, action system, event queue, snapshot builder, LLM mock orchestrator, and tick-loop orchestration.

### Modified Capabilities
- None — existing architecture spec requirements (R5: package structure, R6: ConnectionManager, R7: SQLAlchemy models) are already defined; this change implements against them without altering their spec-level behavior.

## Approach

Implementation order: World grid + resources → Agent dataclass → Action handlers → FSM runner → Event queue → Snapshot builder → SimulationEngine (orchestrator) → FastAPI lifespan integration → WS broadcast integration → MockLLMOrchestrator → SQLite logging → Tests.

All in `backend/app/simulation/`. Zero new dependencies — pure Python stdlib + existing requirements.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/simulation/` | New | 6 new modules: engine, agent, actions, world, event_queue, snapshot |
| `backend/app/main.py` | Modified | Add engine start/stop to FastAPI lifespan |
| `backend/tests/test_engine.py` | New | Integration tests for the engine lifecycle |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Tick loop blocks broadcast | Low | Measured sleep + try/except per tick |
| BFS performance at scale | Low | 50×50 is trivial; monitor if grid grows |
| Agent state complexity | Low | Dataclass keeps it simple; no ECS needed yet |
| No LLM for testing | None | MockLLMOrchestrator enables full testing without LLM |
| Zero new dependencies | None | Reduces integration risk completely |

## Rollback Plan

Revert the two modified files (`main.py` + `__init__.py` if touched) and delete the 6 new simulation modules. No DB migrations, no config changes.

## Dependencies

- Existing project skeleton (R5: `app/simulation/` package, R6: ConnectionManager, R7: SQLAlchemy models)
- Pure Python stdlib + existing `requirements.txt` — no new packages

## Success Criteria

- [ ] Engine starts/stops cleanly with FastAPI lifespan
- [ ] Agents pathfind and perform actions each tick
- [ ] World snapshots broadcast to all connected WS clients
- [ ] Events and metrics logged to SQLite
- [ ] All engine tests pass
