# Delta: combat-system (Modified)

## MODIFIED Requirements

### R10 — Combat Emotion Triggers

Combat events MUST be logged as SimEvents. Additionally, combat outcomes MUST trigger emotion events: `combat_win` triggers `proud`; `combat_loss` triggers `fearful` and `sad`.
(Previously: No emotion triggers on combat outcomes.)

#### Scenario: Combat win triggers proud
- GIVEN an attacker that defeats a target (target.health ≤ 0)
- WHEN the combat death event is processed
- THEN `EmotionManager.apply_trigger(attacker, "combat_win")` is called

#### Scenario: Combat loss triggers fearful and sad
- GIVEN an agent that was defeated in combat (took fatal damage)
- WHEN the death event is processed for the loser
- THEN `EmotionManager.apply_trigger(loser, "combat_loss")` is called before the agent is removed
