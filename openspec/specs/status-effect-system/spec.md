# Spec: status-effect-system

## Purpose

Define temporal buffs/debuffs with duration, stacking rules, and apply/tick/expire lifecycle. Adds emergent consequences from actions, environment, and combat.

## Dependencies

- **Depends on**: simulation-engine, agent-roles
- **Depends on**: data-driven-definitions (DEFINITIONS singleton, YAML loader)

## Capabilities

### capability: status-effects
**Depends on**: simulation-engine, agent-roles, data-driven-definitions

#### Requirements

| # | Description | Strength |
|---|-------------|----------|
| E1 | System MUST load effect templates from `configs/definitions/status_effects.yaml`. Each MUST include: `name`, `category` (buff/debuff/neutral), `duration` (ticks), `max_stacks`, `modifiers` (attribute→delta), optional `triggers` (trigger_type→condition), optional `removal_conditions`. | MUST |
| E2 | Each agent MUST have `active_effects: dict[str, dict]` mapping name → `{remaining_ticks, current_stacks, total_modifiers}`. Effects applied via `StatusEffectManager.apply(agent, effect_name, source)`. If active, refresh duration (additive) and increment stacks (cap at max_stacks). | MUST |
| E3 | Each tick, `StatusEffectManager.process_tick(agent)` MUST decrement all durations by 1. Effects with `remaining_ticks ≤ 0` MUST be removed. `get_total_modifiers(agent)` MUST aggregate active stat modifiers. | MUST |
| E4 | Eating POISONOUS_BERRY MUST apply `poisoned`. Combat critical hit MAY apply `bleeding`. Resting MUST remove `exhausted`. Drinking water MUST apply `hydrated`. | MUST |
| E5 | Same effect → additive duration, capped stacks. Different categories → all apply (strongest-wins for conflicting stat deltas). Same category, different names → additive (e.g. two speed buffs stack). Emotion modifiers compose multiplicatively with status effect modifiers as a separate layer — both feed into the same `get_total_modifiers()` output. | MUST |
| E6 | LLM prompt MUST include `Effects: {name}({remaining_ticks}t),...`. Poison instinct fallback: if `poisoned` AND health < 50%, agent MUST prioritize rest/heal regardless of LLM plan. | MUST |

#### Scenarios

### Scenario: Apply new vs refresh effect
- GIVEN an agent with no active effects
- WHEN apply(agent, "poisoned", source="food") is called
- THEN agent.active_effects["poisoned"] = {remaining_ticks: 20, current_stacks: 1, total_modifiers: {health: -2}}
- WHEN called again with same effect
- THEN remaining_ticks = 40 (additive), stacks = 2 (capped at max_stacks)

### Scenario: Tick expiration
- GIVEN an agent with `poisoned` at 1 remaining tick
- WHEN process_tick() runs
- THEN remaining_ticks becomes 0 and effect is removed

### Scenario: Poison trigger
- GIVEN an agent eating POISONOUS_BERRY (resource with `poisonous: true`)
- WHEN the EAT handler processes consumption
- THEN StatusEffectManager.apply(agent, "poisoned", source="food") is called

### Scenario: Poison instinct fallback
- GIVEN an agent with `poisoned` active, health=40%, in LLM_WAITING
- WHEN _fsm_llm_waiting() checks poison condition
- THEN agent overrides LLM plan and transitions to executing with action_type=REST or HEAL

### Scenario: Emotion and status modifiers compose
- GIVEN an agent with status modifier strength=1.2 (buff active) and emotional modifier strength=1.1 (angry)
- WHEN `get_total_modifiers(agent)` is called
- THEN the effective strength modifier is 1.2 × 1.1 = 1.32

### Scenario: Emotion modifier with no status effect
- GIVEN an agent with no active_effects but emotions={"sad": {"intensity": 0.6}}
- WHEN `get_total_modifiers(agent)` is called
- THEN the result includes emotion-based modifiers only (no status effects)

#### Flow: Effect Tick

```
_tick()
    → _process_needs()
    → StatusEffectManager.process_tick(agent) for each agent
        → for each active_effects entry:
            → remaining_ticks -= 1
            → if ≤ 0: remove
    → (later, FSM runner)
    → _fsm_llm_waiting() checks poison fallback
```
