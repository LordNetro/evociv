# Delta: agent-society (Modified)

## MODIFIED Requirements

### F6-R7 — Socialize Emotion Trigger

All conversation events MUST be recorded as SimEvents. Additionally, successful SOCIALIZE interactions MUST trigger `happy` and `calm` emotion events for both participants.
(Previously: No emotion triggers on socialization.)

#### Scenario: Socialize triggers happiness
- GIVEN two agents that successfully complete a SOCIALIZE interaction
- WHEN the interaction event is logged
- THEN `EmotionManager.apply_trigger(agent_a, "socialize")` AND `EmotionManager.apply_trigger(agent_b, "socialize")` are called

### F4-R7 — Faction Death Emotion Trigger

When a faction member dies, their inventory MUST transfer to shared_resources. Additionally, all faction members MUST receive `sad` and `angry` emotion triggers.
(Previously: No emotion triggers on faction death.)

#### Scenario: Faction death triggers sadness and anger
- GIVEN a faction with 3 members
- WHEN one member dies
- THEN `EmotionManager.apply_trigger(survivor, "faction_death")` is called for each surviving member
