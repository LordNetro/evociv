# Proposal: Map Memory + Fog of War (Backend)

## Intent

Enable per-agent tile memory with fog-of-war data so the frontend can render
only tiles each faction has seen. Existing hooks (`explored_tiles`, `knowledge`,
`share_knowledge`, faction system, `visibility_multiplier` in weather/night
definitions) exist but are disconnected — no pipeline from vision radius
computation through tile memory recording to snapshot delivery.

## Scope

### In Scope

- `TileMemory` dataclass per agent: last-known resource type, amount,
  tick_last_seen, visibility status
- Vision radius computation: Manhattan distance, base=5, modified by weather
  (`visibility_multiplier`) + night (`visibility_multiplier`) + skill effects
- Faction shared tile memory: instant sync when any member discovers/updates
- Snapshot includes per-faction `tile_visibility` with `visible` + `fog` tile
  lists (packed for frontend consumption)
- Engine integration: update agent tile memory on movement and position change
- Tests for all new functionality

### Out of Scope

- Frontend fog rendering (Grid3D/Resources3D shader changes) — deferred
- Per-client WebSocket connections — deferred (use packed per-faction data)
- Fog-of-war exploration UI — deferred
- Tile memory persistence across simulation restarts — deferred

## Capabilities

### New Capabilities

- `map-memory`: Per-agent tile memory with last-known state, vision radius
  computation, faction sync, and snapshot delivery of visible/fog tile lists.

### Modified Capabilities

- None — pure addition; existing systems are unchanged.

## Approach

1. **TileMemory dataclass** in new `backend/app/simulation/map_memory.py`:
   `agent_id, x, y, resource_type, amount, tick_last_seen`.

2. **VisionRadius** static method: `base_radius (5) × weather.visibility_multiplier ×
   time.night.visibility_multiplier × skill_vision_modifier`. Clamp to [1, 15].

3. **FactionMemory** on `Faction` dataclass: `shared_tile_memory:
   dict[tuple[int,int], TileMemory]`. When agent sees tile, upsert into
   faction's shared memory immediately.

4. **Engine hook** in `_fsm_moving` (after position update) and `_tick` (for
   stationary agents every N ticks): compute tiles within vision radius, update
   agent + faction memory.

5. **Snapshot**: add `faction_tile_visibility:
   dict[str, dict[str, list[dict]]]` mapping faction_id → `{visible: [...],
   fog: [...]}`. `visible` = tiles within any member's current vision radius.
   `fog` = tiles in shared memory but not currently visible. Delivered per
   faction in the snapshot broadcast.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/simulation/map_memory.py` | New | TileMemory, VisionRadius, FactionMemory |
| `backend/app/simulation/agent.py` | Modified | Add `tile_memory` field to Agent |
| `backend/app/simulation/faction.py` | Modified | Add `shared_tile_memory` to Faction |
| `backend/app/models/schemas.py` | Modified | Add `faction_tile_visibility` to WorldSnapshot |
| `backend/app/simulation/snapshot.py` | Modified | Build faction_tile_visibility in snapshot |
| `backend/app/simulation/engine.py` | Modified | Hook vision update on movement/tick |
| `backend/tests/` | New/Modified | Tests for new map_memory module + integration |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Tile memory size grows unbounded (50×50=2500 tiles × N factions) | Low | Dict per faction; sent as delta (only changed tiles) in snapshot |
| Performance: vision radius scan every agent move | Med | Precompute tile sets per faction; cache until weather/time changes or agent moves |

## Rollback Plan

- Revert `agent.py`, `faction.py`, `schemas.py`, `snapshot.py`, `engine.py`
  changes.
- Delete new `map_memory.py`.
- Snapshot continues sending `faction_tile_visibility: {}` — frontend
  ignores missing field.

## Dependencies

- Existing: weather/time `visibility_multiplier` definitions, faction system,
  `explored_tiles` field, `knowledge` sharing pipeline.

## Success Criteria

- [ ] Vision radius computation correctly multiplies base × weather × night × skill
- [ ] Agent tile memory records tile state on discovery and position change
- [ ] Faction shared tile memory syncs instantly via member updates
- [ ] Snapshot includes `faction_tile_visibility` with correct visible/fog lists
- [ ] All existing 478 tests pass
