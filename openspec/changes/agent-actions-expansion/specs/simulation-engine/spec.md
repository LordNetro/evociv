# Delta for simulation-engine

> Modifies the simulation engine spec from `openspec/changes/simulation-engine/specs/simulation-engine/spec.md`.
> Rate rebalance, role-driven FSM, 10 new actions in FSM paths, combat interruption, equipment awareness, structure-aware pathfinding.

## ADDED Requirements

### Requirement: Rate Rebalance

Decay rate constants SHALL be changed from their current values to:
- `HUNGER_DECAY`: 0.1 → **0.04** per tick
- `THIRST_DECAY`: 0.15 → **0.06** per tick
- `ENERGY_DECAY`: 0.05 → **0.03** per tick
(Previously: faster decay which forced agents to spend ~80% of ticks on survival.)

#### Scenario: Slower decay gives agents breathing room
- GIVEN an agent with baseline stats
- WHEN 10 ticks pass
- THEN hunger increased by ~0.4 (was 1.0), thirst by ~0.6 (was 1.5), energy decremented by ~0.3 (was 0.5)

### Requirement: Role-Driven FSM Evaluation

The FSM `_fsm_evaluate` method SHALL consult the agent's role priority table when determining action ordering. The role priorities override the hardcoded priority chain. If the role has no entry for a given condition, the FSM falls back to the default chain.
(Previously: all agents used the same hardcoded priority chain.)

#### Scenario: Role-based action prioritization
- GIVEN a `fighter` agent with hunger=50 and a valid ATTACK target nearby, and a `gatherer` agent with same stats
- WHEN both agents' FSM evaluates
- THEN the fighter prioritizes ATTACK (role top priority), while the gatherer prioritizes GATHER (default chain)

#### Scenario: Role fallback to default chain
- GIVEN an agent role whose priority table does not list a condition (e.g., no ATTACK entry)
- WHEN the FSM evaluates that condition
- THEN the FSM uses the default hardcoded chain for that condition

### Requirement: New Actions in FSM Paths

The FSM SHALL support 10 new ActionTypes in its evaluate/moving/executing paths: MINE, HUNT, FISH, FARM, CRAFT, BUILD, ATTACK, GUARD, EXPLORE, HEAL. Each new action SHALL have entries in `get_action_duration()`, `ACTION_EMOJIS`, and `REGISTRY`.

#### Scenario: New action registered and executed
- GIVEN a `miner` agent adjacent to an iron tile
- WHEN the FSM evaluates and selects MINE per role priorities
- THEN the agent transitions through executing with action_type=MINE and completes the action

### Requirement: Combat Interruption

When an agent takes damage (health reduced by any source), the agent's FSM SHALL be interrupted: if in `idle`, `moving`, or `executing` states, the FSM transitions to `evaluate` on the next tick so the agent can react.

#### Scenario: FSM interruption on damage
- GIVEN an agent in `executing` state gathering resources
- WHEN the agent takes 5 combat damage
- THEN on the next tick, the agent's FSM is forced to `evaluate` state

### Requirement: Structure-Aware Pathfinding

The `is_passable` check SHALL treat tiles occupied by wall-type structures as impassable. Other structure types (storage_hut, house, forge, farm) remain passable.

#### Scenario: Wall blocks pathfinding
- GIVEN a wall structure at (10,10)
- WHEN `world.is_passable(10,10)` is called
- THEN it returns False

## MODIFIED Requirements

### FSM Transitions (R4)

FSM with 6 states via `match/case`: IDLE, MOVING, EXECUTING, EVALUATE, LLM_TRIGGER, LLM_WAITING. One handler method per state. Instinct fallback (find nearest food/water/action per role priorities) when no LLM response. Transitions follow the diagram: IDLE→EVALUATE→MOVING/LLM_TRIGGER→LLM_WAITING→IDLE or →MOVING→EXECUTING→EVALUATE.
(Previously: fixed priority chain irrespective of role. Instinct only searched food/water.)

#### Scenario: Role-aware instinct behavior
- GIVEN a `fighter` agent in LLM_WAITING with low energy and a hostile target adjacent
- WHEN instinct fallback triggers
- THEN the fighter MAY ATTACK the hostile target instead of only seeking food/water

### Actions (R5)

Action system: `ActionType` enum (MOVE, CHOP, DRINK, EAT, GATHER, REST, REPRODUCE, TRADE, SOCIALIZE, FEED_CHILD, MINE, HUNT, FISH, FARM, CRAFT, BUILD, ATTACK, GUARD, EXPLORE, HEAL) + `REGISTRY` dict. Handlers mutate agent state and/or inventory.
(Previously: 10 action types. New: MINE, HUNT, FISH, FARM, CRAFT, BUILD, ATTACK, GUARD, EXPLORE, HEAL.)

#### Scenario: All new actions registered
- GIVEN the REGISTRY dict
- WHEN all 10 new ActionTypes are checked
- THEN each has a corresponding handler function registered

### Action Durations (R5 extension)

`get_action_duration()` SHALL include entries for new ActionTypes: MINE `max(2, 8-strength/10)`, HUNT `max(2, 10-speed/10)`, FISH 5, FARM 5, CRAFT (recipe.duration modified by tool/station), BUILD 10, ATTACK 3, GUARD 3, EXPLORE `max(3, 12-speed/10)`, HEAL 5.

#### Scenario: New action durations computed
- GIVEN an agent with strength=60
- WHEN `get_action_duration(MINE, agent)` is called
- THEN duration = max(2, 8 - 60/10) = max(2, 2) = 2 ticks

## REMOVED Requirements

None.
