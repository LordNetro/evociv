# Tasks: Map Memory + Fog of War

## Phase 1: Infrastructure

- [x] 1.1 Create `backend/app/simulation/map_memory.py` with `TileMemory` dataclass and `MapMemoryManager` class (5 static methods: `update_vision`, `get_vision_radius`, `get_visible_tiles`, `sync_to_faction`, `get_faction_tile_visibility`)
- [x] 1.2 Add `tile_memory: dict[tuple[int,int], TileMemory] = field(default_factory=dict)` to `Agent` dataclass in `agent.py`
- [x] 1.3 Add `shared_tile_memory: dict[tuple[int,int], TileMemory]` and `tile_reported_by: dict[tuple[int,int], str]` fields to `Faction` dataclass in `faction.py`
- [x] 1.4 Add `vision_range: 1` to `survival` effects_per_level in `configs/definitions/skills.yaml`
- [x] 1.5 Export `MapMemoryManager` and `TileMemory` from `backend/app/simulation/__init__.py`

## Phase 2: Engine Integration

- [x] 2.1 Call `MapMemoryManager.update_vision()` in engine after resource discovery checks in `_tick()` for all agents every tick
- [x] 2.2 Add `faction_tile_visibility: dict[str, dict[str, list[dict]]]` field to `WorldSnapshot` in `backend/app/models/schemas.py`
- [x] 2.3 Build `faction_tile_visibility` via `get_faction_tile_visibility()` in `snapshot.py` — both `build()` and `build_delta()`
- [x] 2.4 Add `Explored: {count} tiles` line to `STATE_PROMPT_TEMPLATE` in `backend/app/ai/prompts.py` showing `len(agent.tile_memory)`

## Phase 3: Tests

- [x] 3.1 Create `backend/tests/test_map_memory.py` with unit tests for all 5 `MapMemoryManager` methods + integration test for `update_vision` through engine tick

## Phase 4: Validation

- [x] 4.1 Run full test suite: 514 tests passing (478 existing + 36 new)
- [x] 4.2 Verify application starts without errors
