# Spec: emotion-system

> Synced from delta `openspec/changes/emotion-morale-system/specs/emotion-system/spec.md` (2026-05-02)

## Purpose

Define the emotion/morale system: data-driven emotion definitions, intensity lifecycle (apply/decay/remove), trigger-to-delta mapping with cooldown enforcement, modifier aggregation, and LLM prompt integration.

## Dependencies

- **Depends on**: simulation-engine, data-driven-definitions (DEFINITIONS singleton, YAML loader)

## Capabilities

### capability: emotion-system
**Depends on**: simulation-engine, data-driven-definitions

#### Requirements

| # | Requirement | Strength |
|---|-------------|----------|
| E1 | The system MUST load emotion definitions from `configs/definitions/emotions.yaml`. Each emotion MUST include: `name`, `category` (positive/negative/neutral), `icon` (str), `decay_per_tick` (float), `effects` (dict of attribute→multiplier), `triggers` (dict of event_type→intensity_delta). | MUST |
| E2 | Each agent MUST have an `emotions: dict[str, dict]` field tracking current emotional state. Each entry MUST contain `intensity: float (0.0–1.0)` and `last_trigger_tick: int`. Emotions with intensity ≤ 0 MUST be automatically removed. | MUST |
| E3 | When a trigger event occurs (socialize, eat, combat_win, combat_loss, discovery, faction_event, skill_up), the system MUST apply the corresponding intensity delta to the relevant emotion(s), clamped to [0.0, 1.0]. The same trigger MUST NOT fire more than once per 5 ticks per agent per emotion. | MUST |
| E4 | Each tick, `EmotionManager.process_tick()` MUST decrement all active emotion intensities by the emotion's `decay_per_tick` value. Different emotions MUST decay at different rates. Emotions reaching intensity ≤ 0 MUST be removed. | MUST |
| E5 | `EmotionManager.get_total_modifiers(agent)` MUST return a dict of attribute→multiplier combining all active emotions. For the same attribute across multiple emotions, the **strongest** multiplier MUST win (not additive). These modifiers MUST be multiplicative with existing skill and status effect modifiers. Formula: `final_multiplier = skill_mod * status_mod * emotion_mod`. | MUST |
| E6 | The LLM prompt MUST include the agent's emotional state: `Emotional State: Happy (7/10)`. The dominant emotion (highest intensity) MUST be displayed first with its intensity. If no emotions are active, MUST display "Calm". | MUST |

#### Scenarios

### E1 — Emotion Definitions

#### Scenario: Load valid YAML
- GIVEN a valid `configs/definitions/emotions.yaml` with 8 emotions (happy, sad, angry, fearful, calm, hopeful, proud, curious)
- WHEN `EmotionManager.load_definitions()` is called (via DEFINITIONS singleton loading)
- THEN all 8 emotion definitions are loaded with their full fields

#### Scenario: Missing field raises error
- GIVEN an emotion entry in YAML missing the `decay_per_tick` field
- WHEN definitions are loaded
- THEN a `ValueError` is raised with a message identifying the missing field

### E2 — Emotional State Tracking

#### Scenario: New agent has empty emotions
- GIVEN a newly created Agent
- WHEN the agent is initialized
- THEN `agent.emotions == {}`

#### Scenario: Emotion auto-removed at zero
- GIVEN an agent with `happy` at intensity=0.05 and decay_per_tick=0.1
- WHEN `process_tick()` decrements intensity to -0.05
- THEN `happy` is removed from `agent.emotions`

### E3 — Trigger Processing

#### Scenario: Trigger adds intensity
- GIVEN an agent with no active emotions
- WHEN a `combat_win` event triggers and proud has delta=+0.3
- THEN `agent.emotions["proud"]` is created with intensity=0.3

#### Scenario: Trigger clamped at 1.0
- GIVEN an agent with `proud` at intensity=0.9
- WHEN a `combat_win` event triggers with delta=+0.3
- THEN `agent.emotions["proud"].intensity == 1.0`

#### Scenario: Cooldown prevents re-trigger
- GIVEN an agent whose `proud` last_trigger_tick is tick=10
- WHEN a `combat_win` event occurs at tick=12 (only 2 ticks later)
- THEN the trigger is ignored and intensity is NOT modified

#### Scenario: Cooldown expires
- GIVEN an agent whose `proud` last_trigger_tick is tick=10
- WHEN a `combat_win` event occurs at tick=15 (5 ticks later)
- THEN the trigger fires and intensity is modified

### E4 — Emotion Decay

#### Scenario: Different decay rates
- GIVEN an agent with `angry` (decay=0.15) and `happy` (decay=0.05) both at intensity=0.5
- WHEN `process_tick()` runs
- THEN angry drops to 0.35 and happy drops to 0.45

### E5 — Modifier Aggregation

#### Scenario: Strongest modifier wins
- GIVEN an agent with `angry` (strength: 1.2) and `sad` (strength: 0.9)
- WHEN `get_total_modifiers(agent)` is called
- THEN `result["strength"] == 1.2` (strongest wins)

#### Scenario: Different attributes combine independently
- GIVEN an agent with `happy` (speed: 1.1) and `angry` (strength: 1.2)
- WHEN `get_total_modifiers(agent)` is called
- THEN `result["speed"] == 1.1` AND `result["strength"] == 1.2`

#### Scenario: No active emotions returns identity
- GIVEN an agent with `agent.emotions == {}`
- WHEN `get_total_modifiers(agent)` is called
- THEN the result is an empty dict `{}`

#### Scenario: Modifier composes multiplicatively
- GIVEN an agent with skill_mod=1.5, status_mod=1.2, emotion_mod=1.1 for strength
- WHEN the final modifier is computed
- THEN `final = 1.5 * 1.2 * 1.1 = 1.98`

### E6 — LLM Awareness

#### Scenario: Dominant emotion first
- GIVEN an agent with `angry=0.7`, `happy=0.3`, `fearful=0.5`
- WHEN the LLM prompt is built
- THEN the emotional state line reads "Emotional State: Angry (7/10), Fearful (5/10), Happy (3/10)"

#### Scenario: No emotions displays neutral
- GIVEN an agent with `agent.emotions == {}`
- WHEN the LLM prompt is built
- THEN the emotional state line reads "Emotional State: Calm"
