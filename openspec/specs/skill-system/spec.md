# Spec: skill-system

## Purpose

Define skill progression mechanics: XP accrual, level-up computation, modifier queries for action speed, combat damage, and crafting quality. Enables agents to improve at tasks through repeated use.

## Dependencies

- **Depends on**: simulation-engine, agent-roles
- **Depends on**: data-driven-definitions (DEFINITIONS singleton, YAML loader)

## Capabilities

### capability: skill-progression
**Depends on**: simulation-engine, agent-roles, data-driven-definitions

#### Requirements

| # | Description | Strength |
|---|-------------|----------|
| S1 | System MUST load skill definitions from `configs/definitions/skills.yaml`. Each MUST include: `name`, `category` (combat/crafting/survival/social/exploration), `base_xp_per_action` (action→XP map), `effects_per_level` (speed_mult, damage_mult, quality_mult), optional `unlocks` (recipe names). | MUST |
| S2 | Each agent MUST have `skills: dict[str, int]`. On action completion, system MUST award XP to relevant skills. XP thresholds SHOULD follow diminishing curve: L1=100, L2=250, L3=500, L4=1000, L5=2000. Level-up events at severity `warning`. On level-up, `EmotionManager.apply_trigger(agent, "on_skill_up")` MUST be called. | MUST |
| S3 | Duration modifier: `final = max(1, round(base * (1 - 0.05 * skill_level)))`. Combat damage: `final = base_damage * (1 + 0.1 * combat_skill)`. Skill-0 = 1.0x multiplier (zero-sum start). | MUST |
| S4 | LLM prompt MUST include `Skills: {name}:{level},...` (compact, space-separated). LLM SHOULD use skills for informed decisions. | MUST |

#### Scenarios

### Scenario: XP accrual and level-up
- GIVEN an agent with `skills={}` performing CHOP (base XP 5)
- WHEN action completes and SkillManager.award_xp() is called
- THEN agent gains 5 XP in relevant skill; on reaching 100 XP, skill levels to 1 and a warning-severity event is emitted

### Scenario: Skill-modified duration
- GIVEN an agent with `skills={"survival": 5}` performing GATHER (base duration 3)
- WHEN get_action_duration() is called
- THEN final_duration = max(1, round(3 * (1 - 0.05 * 5))) = max(1, round(2.25)) = 2 ticks

### Scenario: Skill-0 produces baseline
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
