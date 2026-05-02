# Tasks: Skill Progression + Status Effects

## Phase 1: YAML + Definition Infrastructure

- [x] 1.1 Add `SkillDef` and `StatusEffectDef` Pydantic models to `backend/app/core/definition_models.py` with all required fields
- [x] 1.2 Update `DefinitionContainer` with `skills: dict[str, SkillDef]` and `status_effects: dict[str, StatusEffectDef]` fields
- [x] 1.3 Add `_YAML_FILES` entries and `_build_definitions()` sections in `backend/app/core/definitions.py`
- [x] 1.4 Create `configs/definitions/skills.yaml` — 8 skills (carpentry/combat/survival/crafting/social/exploration/mining/farming) with categories, xp maps, effects_per_level
- [x] 1.5 Create `configs/definitions/status_effects.yaml` — 8 effects (poisoned/exhausted/well_fed/hydrated/inspired/bleeding/guarding/berserk) with duration, max_stacks, modifiers, triggers

## Phase 2: Agent Dataclass Update

- [x] 2.1 Add `skills: dict[str, int]` and `active_effects: dict[str, dict]` fields (default factory `dict`) to `backend/app/simulation/agent.py` Agent dataclass

## Phase 3: Core Managers

- [x] 3.1 Create `backend/app/simulation/skills.py` — `SkillManager` with static `award_xp()`, `get_speed_modifier()`, `get_combat_modifier()`, `get_crafting_quality()`, XP curve thresholds `[0,100,250,500,1000,2000,4000,...]`, level-up event emission
- [x] 3.2 Create `backend/app/simulation/status_effects.py` — `StatusEffectManager` with static `apply()`, `process_tick()`, `get_total_modifiers()`, `has_effect()`, `remove_effect()`, `clear_all()`, additive duration refresh, capped stacking

## Phase 4: Integration — Actions & Engine

- [x] 4.1 Modify `get_action_duration()` in `actions.py` to multiply by `skill_mod * effect_mod`, floor 1. Add `_skill_for_action()` helper
- [x] 4.2 Modify `handle_eat()` in `actions.py` to apply `poisoned` effect when consuming poisonous berries
- [x] 4.3 In `engine.py` `_tick()`: add `StatusEffectManager.process_tick(agent)` call after `_process_needs()` (step 1.5)
- [x] 4.4 In `engine.py` `_fsm_executing()`: add `SkillManager.award_xp(agent, action_type)` post-hook after handler returns `result.success`
- [x] 4.5 In `engine.py` `_fsm_llm_waiting()`: add poison instinct fallback before existing hunger instinct

## Phase 5: Integration — Combat, Snapshot, Prompts

- [x] 5.1 Add `calculate_melee_damage_with_effects()`/`calculate_ranged_damage_with_effects()` in `combat.py` accepting `attacker: Agent`, multiplying by skill + effect modifiers (old methods preserved for backward compat)
- [x] 5.2 Update `handle_attack()` in `actions.py` to use new `..._with_effects()` damage functions
- [x] 5.3 Add `skills` and `active_effects` to `AgentState` schema in `backend/app/models/schemas.py`
- [x] 5.4 Add `skills` and `active_effects` to `_build_agent_state()` in `backend/app/simulation/snapshot.py`
- [x] 5.5 Add `{skills_line}` and `{effects_line}` placeholders to `STATE_PROMPT_TEMPLATE` in `backend/app/ai/prompts.py`; serialize in `build_agent_prompt()`

## Phase 6: Tests

- [x] 6.1 Create `backend/tests/test_skills.py` — 12 tests (XP award, level-up thresholds, speed/combat/crafting modifiers, zero-skill baseline, skill-unknown fallback, multiple levels)
- [x] 6.2 Create `backend/tests/test_status_effects.py` — 14 tests (apply new/refresh, tick expiration, stacking caps, modifier aggregation, has/remove/clear)
- [x] 6.3 Create `backend/tests/test_actions.py` — 7 tests (duration formula with skill + effect modifiers, poison trigger)
- [x] 6.4 Update `backend/tests/test_combat.py` — 3 new tests for `_with_effects()` methods
- [x] 6.5 Update `backend/tests/test_definitions.py` — 6 new tests (SkillDef/StatusEffectDef model validation, YAML schema tests)

## Phase 7: Validation

- [x] 7.1 Run all tests — **400 passed**, zero regression (358 original + 42 new)
- [x] 7.2 Verify app starts correctly — DEFINITIONS.skills and DEFINITIONS.status_effects loaded OK
