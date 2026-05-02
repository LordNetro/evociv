# Tasks: Emotion/Morale System

## Phase 1: Infrastructure

- [x] 1.1 Add `EmotionDef` model to `backend/app/core/definition_models.py`; add `emotions: dict[str, EmotionDef]` field to `DefinitionContainer`
- [x] 1.2 Add `emotions.yaml` to `_YAML_FILES` list and `_build_definitions()` in `backend/app/core/definitions.py` (mirror `status_effects` pattern)
- [x] 1.3 Create `configs/definitions/emotions.yaml` with 8 emotions (happy, sad, angry, fearful, calm, hopeful, proud, curious), each with category, icon, decay_per_tick, effects, triggers

## Phase 2: Core System

- [x] 2.1 Add `emotions: dict[str, dict] = field(default_factory=dict)` to `Agent` dataclass in `backend/app/simulation/agent.py`
- [x] 2.2 Create `backend/app/simulation/emotions.py` with `EmotionManager` class: `apply_trigger()`, `process_tick()`, `get_total_modifiers()`, `get_dominant_emotion()`, `get_emotional_state_str()`
- [x] 2.3 Create `backend/tests/test_emotions.py` with unit tests for all 5 EmotionManager methods + edge cases (cooldown, clamp, decay, strongest-wins, empty, unknown trigger)

## Phase 3: Engine Integration

- [x] 3.1 Add `EmotionManager.process_tick(agent, tick)` call in `engine.py _tick()` after `StatusEffectManager.process_tick()`
- [x] 3.2 Wire emotion triggers in `engine.py`: `on_skill_up` after XP awarded, `on_discovery` after discovery events, `on_rest` on rest completion
- [x] 3.3 Wire emotion triggers in `engine.py` `_fsm_executing()`: `on_eat`, `on_build_complete` after successful action completion (action handlers lack tick parameter — wired at engine level)
- [x] 3.4 Wire emotion triggers in `engine.py` `_fsm_executing()`: `on_win_combat`, `on_lose_combat` after attack kills target (engine orchestrates combat triggers)
- [x] 3.5 Wire emotion triggers in `conversation.py`: `on_socialize` in `detect_encounters()` when socialize events are created

## Phase 4: Modifier Integration

- [x] 4.1 Update `get_action_duration()` in `actions.py` to multiply `* emotion_mod` (from `EmotionManager.get_total_modifiers().get("speed_multiplier", 1.0)`)
- [x] 4.2 Update `calculate_melee_damage_with_effects()` and `calculate_ranged_damage_with_effects()` in `combat.py` to multiply `* emotion_mod` (from `.get("damage_multiplier", 1.0)`)

## Phase 5: LLM + Snapshot + Schema

- [x] 5.1 Add `{emotional_state}` to `STATE_PROMPT_TEMPLATE` in `backend/app/ai/prompts.py` and inject via `EmotionManager.get_emotional_state_str(agent)`
- [x] 5.2 Add `emotions: dict[str, dict] = {}` field to `AgentState` in `backend/app/models/schemas.py`
- [x] 5.3 Add `emotions` to `_build_agent_state()` in `backend/app/simulation/snapshot.py` (mirror `active_effects` pattern)

## Phase 6: Validation

- [x] 6.1 Run all tests: `python -m pytest tests/ -v` — 422 passed (22 new + 400 existing, zero regression)
- [x] 6.2 Verify app starts correctly — all imports OK, DEFINITIONS loads emotions.yaml
