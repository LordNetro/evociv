# Spec: structures

## Purpose

Define building placement, structure types with distinct functions, World grid integration, and the BUILD action. Structures add persistence to the world — they remain across ticks, affect gameplay mechanics, block pathfinding, and are rendered in snapshots.

## Dependencies

- **Depends on**: simulation-engine

## Capabilities

### capability: structures
**Depends on**: simulation-engine

#### Requirements

| # | Requirement | Strength |
|---|-------------|----------|
| R1 | A `Structure` dataclass MUST exist with fields: `id` (str), `type` (str), `position` (tuple[int,int]), `owner_id` (str), `health` (float), `max_health` (float), and `properties` (dict[str,Any]). | MUST |
| R2 | A new `StructureManager` class in `structures.py` MUST manage all placed structures: add, remove, get_by_id, get_by_owner, get_at_position, list_all. | MUST |
| R3 | A new `BUILD` ActionType MUST be added. The handler receives a `structure_type` from the plan step, verifies resources, and places the structure on an adjacent empty tile. | MUST |
| R4 | BUILD MUST consume resources based on structure type: `storage_hut` (5 wood, 2 stone), `house` (10 wood, 5 stone), `forge` (8 stone, 3 clay), `farm` (5 wood, 2 fiber), `wall` (3 wood, 1 stone per segment). If insufficient resources, return `success=False`. | MUST |
| R5 | `storage_hut` SHALL increase the owner's effective inventory capacity by 100% (each resource stack limit doubles) when the owner is within 3 tiles of the hut. | MUST |
| R6 | `house` SHALL increase the owner's energy recovery when resting: `energy_gain = 10 * 2` (instead of base 10) when resting while on or adjacent to the house tile. | MUST |
| R7 | `forge` MUST be required as a station for metal-crafting recipes (iron_ingot, iron_sword, etc.). It MUST appear in the world grid as a non-blocking tile. | MUST |
| R8 | `farm` SHALL produce 2 `berries` per tick into the owner's inventory when the owner is adjacent to the farm. Production is automatic (no FARM action needed for generation). | MUST |
| R9 | `wall` MUST be an impassable tile (blocked=True). It occupies its grid tile for pathfinding. Wall has `health=50` and can be destroyed by ATTACK actions dealing damage to it. | MUST |
| R10 | The World grid MUST support a `structures` layer: `world.structures` dict mapping `(x,y)` -> `Structure`. Pathfinding (`is_passable`) MUST treat wall tiles as blocked. | MUST |
| R11 | Structures MUST be included in snapshots: a `structures` field in `WorldSnapshot` containing a list of structure dicts with id, type, position, owner, health, and properties. | MUST |
| R12 | Structures MUST have health and be damageable. When `health <= 0`, the structure is destroyed, removed from the grid and manager, and a SimEvent is emitted. | SHOULD |
| R13 | The LLM prompt MUST include nearby structures context so the agent knows what buildings are available. | MUST |
| R14 | Each agent MAY own multiple structures. Structure ownership is tracked via `owner_id`. | MUST |

#### Scenarios

### Scenario: Build storage_hut
- GIVEN an agent with `inventory={"wood": 5, "stone": 2}` at position (10,10) with an empty adjacent tile at (11,10)
- WHEN the agent executes BUILD with `structure_type="storage_hut"` targeting (11,10)
- THEN the tile at (11,10) has a `storage_hut` structure owned by the agent, and the agent's inventory reflects wood:-5, stone:-2

### Scenario: Build fails — insufficient resources
- GIVEN an agent with `inventory={"wood": 3, "stone": 1}`
- WHEN the agent executes BUILD with `structure_type="storage_hut"` (requires 5 wood, 2 stone)
- THEN the action returns `success=False` with reason "insufficient resources"

### Scenario: Build fails — occupied tile
- GIVEN an agent with sufficient resources targeting tile (11,10) which already has a structure or resource
- WHEN the agent executes BUILD targeting (11,10)
- THEN the action returns `success=False` with reason "tile occupied"

### Scenario: Storage_hut capacity bonus
- GIVEN an agent owner standing at (12,10) within 3 tiles of their storage_hut at (11,10)
- WHEN the agent tries to carry more than 50 of any resource
- THEN the effective stack limit is doubled compared to an agent without hut proximity

### Scenario: House energy recovery
- GIVEN an agent on their house tile
- WHEN the agent executes REST
- THEN energy increases by 20 per tick (2x base rate) instead of 10

### Scenario: Forge required for metal crafting
- GIVEN an agent with inventory={"iron_ore": 2, "clay": 1} adjacent to a forge
- WHEN the agent crafts `iron_ingot`
- THEN the craft succeeds (forge satisfies station requirement)

### Scenario: Wall blocks pathfinding
- GIVEN a wall at (5,5)
- WHEN an agent tries to find a path from (5,4) to (5,6)
- THEN the path goes around (5,5) instead of through it

### Scenario: Wall destroyed by combat
- GIVEN a wall at (10,10) with health=50
- WHEN an agent attacks the wall dealing 12 damage
- THEN the wall's health is 38, and the wall is NOT removed
- AND WHEN the wall reaches health=0
- THEN it is removed from the grid and a "structure_destroyed" SimEvent is logged

### Scenario: Farm auto-generates food
- GIVEN a farm structure owned by agent at (15,15), and the agent is adjacent to it
- WHEN 1 tick passes
- THEN the agent's inventory gains 2 berries (automatic, no action required)
- WHEN the agent moves 4 tiles away
- THEN no berries are generated (outside range)

### Scenario: Structure in snapshot
- GIVEN a simulation with 2 structures (house, forge)
- WHEN a WorldSnapshot is built
- THEN the snapshot includes a `structures` field with both structures including their id, type, position, owner_id, health, and properties
