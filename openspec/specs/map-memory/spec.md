# Spec: map-memory

> Delta for `openspec/changes/map-memory-fog-of-war/specs/map-memory/spec.md`

## Purpose

Per-agent tile memory with fog-of-war. Each agent records last-known tile state. Vision radius incorporates weather/night/skill modifiers. Faction shared memory syncs discoveries. Snapshots deliver per-faction visible/fog tile lists.

## Dependencies

- **Depends on**: weather-time-system (visibility_multiplier), agent-society (faction/knowledge), skill-system (survival skill)

## Requirements

### R1 — Tile Memory

| # | Requirement | Strength |
|---|-------------|----------|
| M1a | Each agent MUST have `tile_memory: dict[tuple[int,int], TileMemory]`. | MUST |
| M1b | TileMemory MUST store: `resource_type: str \| None`, `amount: int`, `tick_last_seen: int`. | MUST |
| M1c | On move or sight, agent's tile_memory MUST update to current tile state. | MUST |

#### Scenario: Record tile on move
- GIVEN agent at (5,5) with empty tile_memory moves to (6,5)
- WHEN visible tiles are computed
- THEN tile_memory[(6,5)] = {resource_type, amount, tick}

#### Scenario: Unseen tile preserved
- GIVEN agent at (5,5) with tile_memory[(10,10)] = wood/50/tick=100
- WHEN agent moves to (6,5) and (10,10) is out of range
- THEN tile_memory[(10,10)] is unchanged

### R2 — Vision Radius

| # | Requirement | Strength |
|---|-------------|----------|
| M2a | Vision radius in Manhattan distance, base=5. | MUST |
| M2b | Computation: `max(1, floor(base × night_mult × weather_mult) + floor(skill/5))`, clamped to [1,15]. night=0.7, fog=0.5. | MUST |

#### Scenario: Base radius
- GIVEN day, fair weather, skill=0
- WHEN radius computed
- THEN radius=5

#### Scenario: Night fog with skill
- GIVEN night (×0.7), fog (×0.5), skill=12
- WHEN radius computed
- THEN radius = max(1, floor(5×0.7×0.5) + floor(12/5)) = 3

#### Scenario: Minimum floor
- GIVEN night, fog, skill=0
- WHEN radius computed
- THEN radius = max(1, floor(5×0.7×0.5) + 0) = 1

### R3 — Visible Tiles on Movement

| # | Requirement | Strength |
|---|-------------|----------|
| M3a | On move, compute all tiles with Manhattan distance ≤ vision radius from new position. | MUST |
| M3b | Each visible tile updates agent's tile_memory. | MUST |
| M3c | Newly seen resource subtypes SHOULD be added to agent's `knowledge`. | SHOULD |

#### Scenario: Vision scan
- GIVEN agent at (10,10), vision=3, moves to (12,10)
- WHEN move completes
- THEN all tiles with |x-12|+|y-10| ≤ 3 update tile_memory

#### Scenario: Resource discovery
- GIVEN agent at (5,5), vision=3, tile (7,7) has BERRY/SAFE_BERRY
- WHEN (7,7) is visible
- THEN tile_memory[(7,7)] updates AND "SAFE_BERRY" SHOULD enter agent's knowledge

### R4 — Faction Shared Memory

| # | Requirement | Strength |
|---|-------------|----------|
| M4a | Each faction MUST have `shared_tile_memory: dict[tuple[int,int], TileMemory]`. | MUST |
| M4b | When an agent sees a new or changed tile, faction shared memory MUST update instantly. | MUST |
| M4c | Each entry MUST track `reported_by: str` (agent ID). | MUST |

#### Scenario: New tile syncs to faction
- GIVEN faction F with agent A, empty shared memory
- WHEN A discovers tile (6,5) with wood
- THEN F.shared_tile_memory[(6,5)] = {wood, amount, tick, reported_by=A}

#### Scenario: Changed tile updates faction
- GIVEN F.shared_tile_memory[(6,5)] = wood/30/reported_by=A
- WHEN agent B sees (6,5) with amount=20
- THEN F.shared_tile_memory[(6,5)].amount=20, tick=current, reported_by=B

### R5 — Snapshot Tile Visibility

| # | Requirement | Strength |
|---|-------------|----------|
| M5a | WorldSnapshot MUST have `faction_tile_visibility: dict[str,dict]` keyed by faction_id. | MUST |
| M5b | Each entry: `visible` (tiles within any member's vision) and `fog` (shared memory, not visible). Both `list[dict]`. | MUST |
| M5c | Each tile entry: x, y, resource_type (or null), amount, tick_last_seen. | MUST |

#### Scenario: Visible/fog partition
- GIVEN faction F has 5 shared tiles, 3 in vision of any member
- WHEN snapshot built
- THEN faction_tile_visibility["F"] = {"visible": [3 tiles], "fog": [2 tiles]}

#### Scenario: Empty faction
- GIVEN faction with empty shared_tile_memory
- WHEN snapshot built
- THEN faction_tile_visibility["F"] = {"visible": [], "fog": []}

### R6 — LLM Context

| # | Requirement | Strength |
|---|-------------|----------|
| M6a | LLM prompt MUST include `Explored: {count} tiles` where count = len(faction.shared_tile_memory). | MUST |

#### Scenario: Explored count
- GIVEN agent's faction has 42 tiles in shared_tile_memory
- WHEN LLM prompt is built
- THEN prompt includes "Explored: 42 tiles"
