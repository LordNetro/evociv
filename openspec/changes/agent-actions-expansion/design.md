# Design: Agent Actions Expansion

## Technical Approach

Five independent phases, each adding a module (additive), none modifying existing handler signatures. Role data is Python dicts (same pattern as `ACTION_EMOJIS`). New action handlers match the existing `ActionHandler` signature. Structures live in a new `World.structures` dict. All new systems expose pure functions for unit testability.

## Architecture Decisions

| Option | Tradeoffs | Decision |
|--------|-----------|----------|
| Role storage: JSON vs Python dict | JSON hot-reloadable but breaks strict TDD (file I/O) | **Dicts in `config/roles.py`** — matches existing hardcoded pattern |
| FSM evaluate: if/elif chain per role vs priority data table | Chain is rigid; data table is generic + testable | **Priority data table** — `ROLES[role].priorities` iterated generically |
| Crafting: inline vs `CraftingManager` class | Inline inflates handler; class is testable in isolation | **`CraftingManager`** in `crafting.py` |
| Structures: Tile.blocked flag vs `World.structures` dict | Tile coupling pollutes Tile; separate dict is clean | **`World.structures: dict[tuple,int], Structure]`** |
| Combat: `CombatManager` class vs engine method | Engine coupling grows; manager is pure + testable | **`CombatManager`** in `combat.py` |
| Prompt: static enum vs per-role dynamic | Static breaks role differentiation; dynamic matches new design | **Role-filtered action list in `JSON_FORMAT_INSTRUCTION`** |

## Data Flow

```
Tick
 ├─ _process_needs()         [new decay rates: 0.04/0.06/0.03]
 ├─ _run_agent_fsm()
 │   ├─ idle → evaluate
 │   ├─ evaluate(): ROLES[role].priorities loop
 │   │   ├─ survival first (eat/drink)
 │   │   ├─ role-specific (builder→BUILD, fighter→GUARD)
 │   │   └─ LLM trigger → llm_trigger
 │   ├─ executing(): REGISTRY[action]()
 │   │   ├─ CRAFT  → CraftingManager.craft()
 │   │   ├─ BUILD  → World.place_structure()
 │   │   ├─ ATTACK → CombatManager.attack()
 │   │   └─ MINE/HUNT/FISH/FARM → tile handlers
 │   └─ moving(): BFS + structure collision check
 ├─ detect_encounters + trades
 ├─ World.regenerate_resources()  [+new resources]
 └─ snapshot build [+equipped items, +structures]
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/config/roles.py` | Create | Role definitions: priorities, stat modifiers, allowed actions |
| `backend/app/simulation/roles.py` | Create | Role lookup, priority evaluation engine, stat application |
| `backend/app/simulation/crafting.py` | Create | `Recipe` dataclass, `CraftingManager`, recipe registry, tool modifiers |
| `backend/app/simulation/structures.py` | Create | `Structure` dataclass, placement validation, bonus functions |
| `backend/app/simulation/combat.py` | Create | `CombatManager`, weapon/armor stats tables, damage formula |
| `backend/app/simulation/actions.py` | Modify | +10 ActionTypes, handlers, duration formulas, emojis, energy costs |
| `backend/app/simulation/agent.py` | Modify | `equipped_weapon`, `equipped_armor`, `experience` fields on Agent |
| `backend/app/simulation/world.py` | Modify | `structures` dict, new resource types (iron_ore, clay, sand, fiber, flint) |
| `backend/app/simulation/engine.py` | Modify | Generic `_fsm_evaluate()` via role priorities, new decay constants, combat phase |
| `backend/app/simulation/snapshot.py` | Modify | `StructureUpdate` in snapshots, new AgentState fields |
| `backend/app/models/schemas.py` | Modify | +`StructureUpdate`, +`equipped_weapon`/`equipped_armor` on AgentState |
| `backend/app/ai/prompts.py` | Modify | Role-filtered action enum in `JSON_FORMAT_INSTRUCTION` |
| `backend/app/simulation/__init__.py` | Modify | Export new modules |
| `backend/app/simulation/event_queue.py` | Modify | +`"violence"` death cause, +`"craft"`/`"build"`/`"fight"` event types |

## Key Data Structures

```python
# config/roles.py
RoleDef = {
    "priorities": list[tuple[str, ActionType]],  # (condition_expr, action)
    "available_actions": list[ActionType],
    "stat_modifiers": dict[str, int],
    "tool_allowlist": list[str],  # item IDs
}
ROLES: dict[str, RoleDef] = {
    "gatherer": {
        "priorities": [],  # empty → falls back to old survival chain
        "available_actions": [MINE, CHOP, GATHER, ...],
        "stat_modifiers": {},
    },
    "builder": {
        "priorities": [
            ("energy > 70 and inventory.wood > 10", BUILD),
            ("inventory.wood < 10", CHOP),
        ],
        "available_actions": [BUILD, CHOP, MINE, ...],
        "stat_modifiers": {"strength": +10},
    },
    "fighter": {
        "priorities": [
            ("health < 30", HEAL),
            ("target_nearby and relationship < -0.3", ATTACK),
        ],
        "available_actions": [ATTACK, GUARD, HEAL, ...],
        "stat_modifiers": {"strength": +15, "speed": +5},
    },
    "scout": {
        "priorities": [("true", EXPLORE)],
        "available_actions": [EXPLORE, MOVE, ...],
        "stat_modifiers": {"speed": +15, "intelligence": +5},
    },
}
DEFAULT_ROLE = "gatherer"  # preserves exact old behavior

# crafting.py
@dataclass
class Recipe:
    id: str
    category: str  # tool | weapon | armor | material | structure | food
    ingredients: dict[str, int]
    tools_required: list[str]
    workbench_required: bool
    duration: int
    energy_cost: int
    result_item: str
    result_quantity: int = 1
    stat_modifiers: dict[str, int] = field(default_factory=dict)

# structures.py
@dataclass
class Structure:
    id: str
    structure_type: str  # house | storage | forge | farm | wall
    position: tuple[int, int]
    owner_id: str | None = None
    blocks_movement: bool = True
    health: int = 100
    capacity: int = 0       # storage capacity
    rest_bonus: float = 0.0 # house: energy recovery multiplier
    workbench: bool = False  # forge: enables crafting recipes
    yield_bonus: float = 0.0 # farm: resource yield multiplier
```

## Key Algorithms

**Generic priority evaluation** (`_fsm_evaluate` → role-driven):
```
for condition_expr, action_type in ROLES[agent.role].priorities:
    if eval(condition_expr, agent, world):
        execute action_type → moving/executing
        return
# fall through to old survival chain (backward compatible)
```

**Damage formula** (`CombatManager.attack`):
```
base_damage = attacker.strength * 0.3 + weapon_damage
mitigation = target.strength * 0.1 + armor_rating
final_damage = max(1, base_damage - mitigation)
target.health -= final_damage
# relationship impact: target.relationships[attacker].score -= 0.5
if target.health <= 0:
    mark death with cause="violence"
```

**Crafting validation** (`CraftingManager.craft`):
```
def craft(agent, recipe_id, workbench_pos=None) -> ActionResult:
    recipe = RECIPES[recipe_id]
    check workbench_required → proximity to Structure(workbench=True)
    check tools_required → agent.inventory or equipped
    check ingredients → agent.inventory[item] >= qty
    deduct ingredients
    agent.action_duration = recipe.duration
    agent.energy -= recipe.energy_cost
    add recipe.result_item × result_quantity to inventory
    if recipe.stat_modifiers: apply to agent attributes
```

## Snapshot Changes

New fields on `AgentState`:
- `equipped_weapon: str | None`
- `equipped_armor: str | None`
- `experience: int = 0`

New schema `StructureUpdate`:
```python
class StructureUpdate(BaseModel):
    id: str
    structure_type: str
    x: int
    y: int
    owner_id: str | None = None
    health: int = 100
    blocks_movement: bool = True
```

`WorldSnapshot` gets `structures: list[StructureUpdate] = []`. Delta tracking via `World.dirty_structures: set[str]`.

## Phase Plan

| Phase | Modules | New Actions | Test Count |
|-------|---------|-------------|------------|
| 1 — Foundation | `config/roles.py`, `engine.py` (rates) | MINE, EXPLORE | +15 |
| 2 — Crafting | `crafting.py`, tool modifiers | CRAFT, HUNT, FISH | +20 |
| 3 — Structures | `structures.py`, World integration | BUILD, FARM | +15 |
| 4 — Combat | `combat.py`, weapons/armor | ATTACK, GUARD, HEAL | +15 |
| 5 — Polish | `prompts.py`, `snapshot.py`, balance | — | +10 |

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Role priority ordering | Parametrize: agent + role → expected next action |
| Unit | Crafting validation | Recipe OK, missing ingredient, missing tool, missing workbench |
| Unit | Structure placement | Valid tile, blocked tile, overlapping structure, out of bounds |
| Unit | Combat formula | Zero weapon, max armor, edge cases (exact kill, 0 damage clamp) |
| Unit | MINE/HUNT/FISH handlers | Resource present, resource depleted, wrong tile type |
| Unit | Explore logic | Path generation to undiscovered tile, boundary handling |
| Unit | Generic _fsm_evaluate | Default gatherer produces same output as old chain |
| Integration | Engine with role-differentiated agents | 2 agents same sim, different roles → different actions |
| Integration | Craft → tool → CHOP faster | Tool modifier applied to duration formula |
| Integration | BUILD → structure blocks BFS | Path blocked by wall, alternative route found |

## Migration / Rollout

No migration required — everything is in-memory. Phase 1 changes decay constants globally (existing tests assert decay happens, not exact values). New agent fields default to `None`/`0`.

## Open Questions

- [ ] Guard state AI: should GUARD be a persistent FSM substate or a periodic action? Decision: action with cooldown + proximity check.
- [ ] HEAL formula: flat heal vs percentage of missing health? Decision: `10 + intelligence * 0.1`, costing 1 berries.
- [ ] Farm yield: per-tick or per-planting? Decision: once per FARM action, scales with adjacent water tiles.
