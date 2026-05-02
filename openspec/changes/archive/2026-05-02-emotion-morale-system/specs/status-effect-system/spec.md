# Delta: status-effect-system (Modified)

## MODIFIED Requirements

### E5 — Modifier Composition with Emotions

Same effect → additive duration, capped stacks. Different categories → all apply (strongest-wins for conflicting stat deltas). Same category, different names → additive (e.g. two speed buffs stack). Emotion modifiers compose multiplicatively with status effect modifiers as a separate layer — both feed into the same `get_total_modifiers()` output.
(Previously: Only status effects were considered. Emotion modifier composition is new.)

#### Scenario: Emotion and status modifiers compose
- GIVEN an agent with status modifier strength=1.2 (buff active) and emotional modifier strength=1.1 (angry)
- WHEN `get_total_modifiers(agent)` is called
- THEN the effective strength modifier is 1.2 × 1.1 = 1.32

#### Scenario: Emotion modifier with no status effect
- GIVEN an agent with no active_effects but emotions={"sad": {"intensity": 0.6}}
- WHEN `get_total_modifiers(agent)` is called
- THEN the result includes emotion-based modifiers only (no status effects)
