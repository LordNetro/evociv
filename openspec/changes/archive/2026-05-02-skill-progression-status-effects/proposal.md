# Proposal: Skill Progression + Status Effects

## Intent

Add two complementary systems that deepen agent simulation. **Skill Progression** lets agents improve at tasks through repeated use, affecting speed, quality, and capability access. **Status Effects** adds temporal buffs/debuffs from actions, environment, and combat. Together they create emergent depth: experienced agents perform better, and consequences of actions linger.

## Scope

### In Scope
- SkillManager: XP accrual, level-up computation, modifier queries (8 skills)
- StatusEffectManager: apply, tick, expire, stacking (additive/multiplicative/strongest-wins)
- 2 new YAML defs: `skills.yaml` (thresholds, base XP), `status_effects.yaml` (templates, duration, stack rules)
- Integration: action duration, combat damage, crafting gates, LLM prompt, WebSocket snapshot
- POISONOUS_BERRY → Poisoned effect chain
- Full test coverage for both managers

### Out of Scope
- Frontend UI for skills/effects bars/icons — deferred to graphical change
- Skill-based recipe unlocks (`recipe.skill_gate` YAML field exists but unused)
- Agent specialization UI (choosing skill focus)
- Hot-reload of YAML definitions
- Skill persistence across restart (RAM-only, SQLite logging)

## Capabilities

> Contract between proposal and specs phases.

### New Capabilities
- `skill-progression`: Skill leveling via XP, modifier computation, level-up events at severity "warning"
- `status-effects`: Temporal buffs/debuffs with duration, stacking rules, apply/tick/expire lifecycle

### Modified Capabilities
- `combat-system`: Damage formulas gain skill multiplier (Combat skill) and effect modifiers (Berserk +damage, Poisoned -Atk)
- `crafting-system`: Crafting quality/speed affected by Crafting skill; recipe `skill_gate` validated
- `architecture` (simulation-engine): Tick loop invokes SkillManager + StatusEffectManager each tick
- `agent-roles`: LLM prompt includes compact skills line + active effects (non-zero only)

## Approach

Dedicated manager classes (pattern: CombatManager, CraftingManager). Both instantiated by Engine, invoked each tick. Skill XP hooks into `_fsm_executing` post-completion. Effects hook into action consumption (eat), combat (damage), and FSM (tick-based expiration). Data-driven via YAML loaded through existing DEFINITIONS singleton. Skill-0 = multiplier 1.0 (zero-sum at start). Poison instinct fallback: if poisoned + health < 50%, auto-prioritize rest regardless of LLM.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/simulation/skills.py` | New | SkillManager class |
| `backend/app/simulation/status_effects.py` | New | StatusEffectManager class |
| `configs/definitions/skills.yaml` | New | 8 skill definitions |
| `configs/definitions/status_effects.yaml` | New | Effect templates |
| `backend/app/simulation/agent.py` | Modify | Add `skills: dict`, `active_effects: dict` |
| `backend/app/simulation/actions.py` | Modify | `get_action_duration()` includes skill+effect mods |
| `backend/app/simulation/engine.py` | Modify | Tick loop calls both managers |
| `backend/app/simulation/combat.py` | Modify | Skill-scaled damage formulas |
| `backend/app/simulation/crafting.py` | Modify | Skill gates on recipe validation |
| `backend/app/core/definition_models.py` | Modify | Add SkillDef, StatusEffectDef models |
| `backend/app/core/definitions.py` | Modify | Load skills.yaml + status_effects.yaml |
| `backend/app/models/schemas.py` | Modify | AgentState adds skills/effects |
| `backend/app/simulation/snapshot.py` | Modify | Include skills/effects in snapshot |
| `backend/app/ai/prompts.py` | Modify | Skills+effects in LLM context |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Prompt size inflation (~200-400 tokens) | High | Compact format: `Carpentry:5, Combat:3`; only non-zero effects |
| Poisoned agents dying off-screen | Medium | Warning events + poison instinct fallback (auto-rest at <50% HP) |
| Balance via XP rates across actions | Medium | Data-driven YAML — tune per skill without code changes |
| Skill-0 regression in tests | Low | Skill-0 = multiplier 1.0 — existing tests break-zero defense |

## Rollback Plan

Revert all touched files: delete `skills.py`, `status_effects.py`, both YAML files; reverse changes in `agent.py`, `actions.py`, `engine.py`, `combat.py`, `crafting.py`, `prompts.py`, `schemas.py`, `snapshot.py`. Validation gate: all existing tests must pass before merge — rollback restores that baseline.

## Dependencies

- **Data-Driven Definitions (Fase 0)**: DEFINITIONS singleton, YAML loader, Pydantic models — already complete

## Success Criteria

- [ ] All existing tests pass (regression: zero)
- [ ] Skill XP accrual tests: XP added per action, level-up at threshold
- [ ] Skill modifier tests: level 0 = 1.0x, level 5 = faster crafting
- [ ] Status effect apply/tick/expire lifecycle tests
- [ ] Status effect stacking tests (additive same-type, strongest-wins different categories)
- [ ] Eating POISONOUS_BERRY triggers Poisoned effect
- [ ] Agent skills appear in LLM prompt in compact format
- [ ] Status effects appear in WebSocket snapshot
