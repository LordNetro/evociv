# Delta: skill-system (Modified)

## MODIFIED Requirements

### S2 — Level-Up Emotion Trigger

Each agent MUST have `skills: dict[str, int]`. On level-up, the system MUST emit an event and trigger `proud` and `curious` emotion events.
(Previously: Level-up emitted event but no emotion triggers.)

#### Scenario: Level-up triggers proud and curious
- GIVEN an agent whose skill XP reaches the next level threshold
- WHEN `SkillManager.award_xp()` triggers a level-up
- THEN `EmotionManager.apply_trigger(agent, "skill_up")` is called
