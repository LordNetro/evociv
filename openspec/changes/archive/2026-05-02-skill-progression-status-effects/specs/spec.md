# Delta Spec: skill-progression-status-effects

## Domain: skill-system (ADDED)

### Requirements

| # | Description | Strength |
|---|-------------|----------|
| S1 | System MUST load skill definitions from `configs/definitions/skills.yaml`. Each MUST include: `name`, `category` (combat/crafting/survival/social/exploration), `base_xp_per_action` (action→XP map), `effects_per_level` (speed_mult, damage_mult, quality_mult), optional `unlocks` (recipe names). | MUST |
| S2 | Each agent MUST have `skills: dict[str, int]`. On action completion, system MUST award XP to relevant skills. XP thresholds SHOULD follow diminishing curve: L1=100, L2=250, L3=500, L4=1000, L5=2000. Level-up events at severity `warning`. | MUST |
| S3 | Duration modifier: `final = max(1, round(base * (1 - 0.05 * skill_level)))`. Combat damage: `final = base_damage * (1 + 0.1 * combat_skill)`. Skill-0 = 1.0x multiplier (zero-sum start). | MUST |
| S4 | LLM prompt MUST include `Skills: {name}:{level},...` (compact, space-separated). LLM SHOULD use skills for informed decisions. | MUST |

#### Scenarios

**S2 — XP accrual and level-up**
- GIVEN an agent with `skills={}` performing CHOP (base XP 5)
- WHEN action completes and SkillManager.award_xp() is called
- THEN agent gains 5 XP in relevant skill; on reaching 100 XP, skill levels to 1 and a warning-severity event is emitted

**S3 — Skill-modified duration**
- GIVEN an agent with `skills={"survival": 5}` performing GATHER (base duration 3)
- WHEN get_action_duration() is called
- THEN final_duration = max(1, round(3 * (1 - 0.05 * 5))) = max(1, round(2.25)) = 2 ticks

**S3 — Skill-0 produces baseline**
- GIVEN an agent with skill level 0 in combat
- WHEN damage is calculated
- THEN multiplier = 1.0, no change from base formula

#### Flow: Skill XP

```
action completes → _fsm_executing() post-hook
    → SkillManager.award_xp(agent, action_type)
    → lookup base_xp from skills.yaml
    → agent.skills[skill] += xp
    → if xp >= threshold[level+1]:
        → skill level up
        → emit event("warning", "{skill} reached level {n}")
```

## Domain: status-effect-system (ADDED)

### Requirements

| # | Description | Strength |
|---|-------------|----------|
| E1 | System MUST load effect templates from `configs/definitions/status_effects.yaml`. Each MUST include: `name`, `category` (buff/debuff/neutral), `duration` (ticks), `max_stacks`, `modifiers` (attribute→delta), optional `triggers` (trigger_type→condition), optional `removal_conditions`. | MUST |
| E2 | Each agent MUST have `active_effects: dict[str, dict]` mapping name → `{remaining_ticks, current_stacks, total_modifiers}`. Effects applied via `StatusEffectManager.apply(agent, effect_name, source)`. If active, refresh duration (additive) and increment stacks (cap at max_stacks). | MUST |
| E3 | Each tick, `StatusEffectManager.process_tick(agent)` MUST decrement all durations by 1. Effects with `remaining_ticks ≤ 0` MUST be removed. `get_total_modifiers(agent)` MUST aggregate active stat modifiers. | MUST |
| E4 | Eating POISONOUS_BERRY MUST apply `poisoned`. Combat critical hit MAY apply `bleeding`. Resting MUST remove `exhausted`. Drinking water MUST apply `hydrated`. | MUST |
| E5 | Same effect → additive duration, capped stacks. Different categories → all apply (strongest-wins for conflicting stat deltas). Same category, different names → additive (e.g. two speed buffs stack). | MUST |
| E6 | LLM prompt MUST include `Effects: {name}({remaining_ticks}t),...`. Poison instinct fallback: if `poisoned` AND health < 50%, agent MUST prioritize rest/heal regardless of LLM plan. | MUST |

#### Scenarios

**E2 — Apply new vs refresh effect**
- GIVEN an agent with no active effects
- WHEN apply(agent, "poisoned", source="food") is called
- THEN agent.active_effects["poisoned"] = {remaining_ticks: 20, current_stacks: 1, total_modifiers: {health: -2}}
- WHEN called again with same effect
- THEN remaining_ticks = 40 (additive), stacks = 2 (capped at max_stacks)

**E3 — Tick expiration**
- GIVEN an agent with `poisoned` at 1 remaining tick
- WHEN process_tick() runs
- THEN remaining_ticks becomes 0 and effect is removed

**E4 — Poison trigger**
- GIVEN an agent eating POISONOUS_BERRY (resource with `poisonous: true`)
- WHEN the EAT handler processes consumption
- THEN StatusEffectManager.apply(agent, "poisoned", source="food") is called

**E6 — Poison instinct fallback**
- GIVEN an agent with `poisoned` active, health=40%, in LLM_WAITING
- WHEN _fsm_llm_waiting() checks poison condition
- THEN agent overrides LLM plan and transitions to executing with action_type=REST or HEAL

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

## Domain: agent-attributes (MODIFIED)

### Requirement: Agent Dataclass (A1)

The Agent dataclass MUST be extended with `skills: dict[str, int]` (default empty) and `active_effects: dict[str, dict]` (default empty). The WebSocket snapshot MUST include both fields. The AgentState schema MUST be updated accordingly.

(Previously: Agent had no skills or active_effects fields.)

#### Scenario: New agent fields initialized
- GIVEN a new Agent created via AgentFactory.from_config()
- WHEN the agent is initialized
- THEN agent.skills == {} AND agent.active_effects == {}

#### Scenario: Snapshot includes fields
- GIVEN an agent with skills={"combat": 3} and active_effects={"poisoned": {...}}
- WHEN WorldSnapshotBuilder.build() is called
- THEN the resulting AgentState includes `skills` and `active_effects`

## Domain: simulation-engine (MODIFIED)

### Requirement: Engine Integration (E7)

The tick loop (`_tick()`) MUST call `StatusEffectManager.process_tick(agent)` for each agent after `_process_needs()` (step 1) and before FSM execution (step 2). The `_fsm_executing()` post-completion hook MUST call `SkillManager.award_xp(agent, action_type)` after action handler completes. The `_fsm_llm_waiting()` MUST check poison fallback condition (E6) during instinct behavior.

(Previously: no skill or status effect processing existed.)

#### Scenario: Tick order preserved
- GIVEN the tick loop at step 1.5
- WHEN _tick() runs
- THEN status effects are processed AFTER need decays but BEFORE FSM execution

#### Scenario: XP awarded on action completion
- GIVEN an agent completing a CHOP action in _fsm_executing()
- WHEN the handler returns success=True
- THEN SkillManager.award_xp(agent, ActionType.CHOP) is called before advancing the plan

---

## Sequence Diagrams

### Skill XP Flow

```
_fsm_executing()
  │ handler(agent, world) → ActionResult
  │ SkillManager.award_xp(agent, action_type)
  │   ├─ skills.yaml: base_xp_per_action[action] → xp
  │   ├─ agent.skills[skill] += xp
  │   └─ if agent.skills[skill] ≥ threshold[level+1]:
  │        level += 1
  │        event_queue.push("skill_up", severity="warning")
  └─ plan_step_index += 1
```

### Effect Tick Flow

```
_tick()
  │ _process_needs()  [step 1]
  │ [NEW] StatusEffectManager.process_tick(agent)  [step 1.5]
  │   ├─ for each name, data in agent.active_effects:
  │   │   data.remaining_ticks -= 1
  │   │   if data.remaining_ticks ≤ 0: del agent.active_effects[name]
  │   └─ aggregate modifiers → get_total_modifiers()
  │
  │ _run_agent_fsm(agent)  [step 2]
  │   ├─ _fsm_executing():
  │   │   handler(agent, world) → result
  │   │   [NEW] SkillManager.award_xp(agent, action_type)
  │   │   ...
  │   └─ _fsm_llm_waiting():
  │       [NEW] if agent has "poisoned" AND agent.health < 50:
  │           override → REST/HEAL
```
