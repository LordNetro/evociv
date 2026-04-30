# Spec: resources-extended

## Purpose

Extend world resources and actions with new resource types (iron, clay, sand, fiber) and four new gather actions: MINE, HUNT, FISH, FARM. Enables a richer resource economy that feeds into the crafting system.

## Dependencies

- **Depends on**: simulation-engine, agent-roles

## Capabilities

### capability: resources-extended
**Depends on**: simulation-engine, agent-roles

#### Requirements

| # | Requirement | Strength |
|---|-------------|----------|
| R1 | Four new resource types MUST be added to the `ResourceType` enum: `IRON`="iron", `CLAY`="clay", `SAND`="sand", `FIBER`="fiber". Existing enum values (TREE, WATER, BERRIES, STONE) remain unchanged. | MUST |
| R2 | World generation MUST place: `iron` deposits (10 tiles, amount 5-15, regen 0), `clay` deposits (15 tiles, amount 8-20, regen 0.005), `sand` deposits (15 tiles, amount 10-25, regen 0.005), `fiber` plants (20 tiles, amount 3-8, regen 0.03). | MUST |
| R3 | A new `MINE` ActionType MUST be added. It extracts resources from nearby mineral tiles: `iron`, `stone`, `clay`, `sand`. Each MINE action produces 1-3 units based on the tile's amount and the agent's strength. | MUST |
| R4 | A new `HUNT` ActionType MUST be added. It targets `animal` tiles (new world feature: deer, rabbit, boar). Each HUNT action produces 1-3 `meat` and 0-1 `hide`. HUNT requires a weapon equipped (fist deals 0 damage to animals — HUNT fails with fist). HUNT consumes 1 arrow if using bow. | MUST |
| R5 | A new `FISH` ActionType MUST be added. It targets water tiles. Each FISH action produces 1 `fish`. FISH requires a tool (spear or fishing_rod) equipped. | MUST |
| R6 | A new `FARM` ActionType MUST be added. It targets farm structures or tilled tiles. Each FARM action produces 3 `berries` or vegetables and consumes 5 ticks. FARM requires the agent to be adjacent to the farm structure. | MUST |
| R7 | Animal tiles SHALL be a new resource type with behavior: animals spawn on empty grass tiles, flee (move to adjacent tile) when an agent approaches within 3 tiles, and have a limited amount (1-3) that depletes with each HUNT. | SHOULD |
| R8 | Each new resource tile MUST follow existing regen mechanics (`regen_rate` per tick, capped at `max_amount`). Non-regen resources (iron) deplete permanently when mined. | MUST |
| R9 | The new resources MUST be usable in crafting recipes: `iron_ore` -> iron_ingot, `clay` -> pottery/bricks, `sand` -> glass, `fiber` -> rope. | MUST |
| R10 | The `get_nearby_resources` method SHALL include new resource types in its results. The LLM prompt SHALL reflect available resource types including animals. | MUST |
| R11 | MINE, HUNT, FISH, FARM SHALL have action durations: MINE (max(2, 8 - strength/10)), HUNT (max(2, 10 - speed/10)), FISH (5 ticks), FARM (5 ticks). | SHOULD |
| R12 | HUNT and FISH actions SHALL decrement the agent's energy by 5 and 3 respectively (in addition to normal energy decay). | SHOULD |

#### Scenarios

### Scenario: Mine iron
- GIVEN an agent with `strength=60` adjacent to an iron deposit with amount=10
- WHEN the agent executes MINE on the iron tile
- THEN the agent gains 1-3 `iron_ore` in inventory (based on strength), the tile amount decreases accordingly, and the action returns `success=True`

### Scenario: Mine fails — no mineral tile
- GIVEN an agent on a tile with no mineral resource
- WHEN the agent executes MINE
- THEN the action returns `success=False` with reason "no minable resource nearby"

### Scenario: Hunt with bow
- GIVEN an agent with `bow` equipped and 5 arrows, adjacent to an animal tile (deer) with amount=2
- WHEN the agent executes HUNT
- THEN the agent gains 2 `meat` and 1 `hide`, consumes 1 arrow, and the animal amount decreases

### Scenario: Hunt with fist fails
- GIVEN an agent with no weapon equipped (fist)
- WHEN the agent executes HUNT
- THEN the action returns `success=False` with reason "cannot hunt without weapon"

### Scenario: Fish with spear
- GIVEN an agent with `spear` equipped adjacent to a water tile
- WHEN the agent executes FISH
- THEN the agent gains 1 `fish` in inventory

### Scenario: Fish without tool fails
- GIVEN an agent with no tool equipped adjacent to water
- WHEN the agent executes FISH
- THEN the action returns `success=False` with reason "fishing requires a tool"

### Scenario: Farm at farm structure
- GIVEN an agent adjacent to a farm structure they own
- WHEN the agent executes FARM
- THEN after 5 ticks, the agent gains 3 `berries` in inventory

### Scenario: Farm without structure fails
- GIVEN an agent on a tile with no farm structure
- WHEN the agent executes FARM
- THEN the action returns `success=False` with reason "no farm structure nearby"

### Scenario: New resources in snapshot
- GIVEN a world with iron, clay, sand, fiber tiles
- WHEN a WorldSnapshot is built
- THEN the tiles include the new resource types with their type, amount, and position

### Scenario: New resources in nearby search
- GIVEN a world with an iron deposit at (12,12) and an agent at (10,10)
- WHEN `world.get_nearby_resources((10,10), radius=5)` is called
- THEN the results include the iron deposit at (12,12)
