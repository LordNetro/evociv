# Delta: simulation-engine (Modified)

## MODIFIED Requirements

### E7 — Engine Emotion Tick Integration

The tick loop MUST call `EmotionManager.process_tick()` for each agent after status effects processing and before FSM execution. Action completion MUST trigger relevant emotion events based on the action type and result.
(Previously: Tick loop had no emotion processing.)

#### Scenario: Emotion tick runs in correct order
- GIVEN the simulation tick loop processing agents
- WHEN the tick executes
- THEN `StatusEffectManager.process_tick()` runs first, THEN `EmotionManager.process_tick()` for each agent, THEN FSM execution begins

#### Scenario: Combat action triggers emotion
- GIVEN an agent completing an ATTACK action against a hostile target
- WHEN the action handler returns `ActionResult(success=True)`
- THEN `EmotionManager.apply_trigger(agent, "combat_win")` is called

#### Scenario: Failed combat triggers negative emotion
- GIVEN an agent that lost a combat encounter (health dropped to critical)
- WHEN the damage handler detects the agent was the loser
- THEN `EmotionManager.apply_trigger(agent, "combat_loss")` is called

#### Scenario: Eat action triggers calm
- GIVEN an agent completing an EAT action successfully
- WHEN the action completes
- THEN `EmotionManager.apply_trigger(agent, "eat")` is called

#### Scenario: Socialize triggers happy
- GIVEN two agents completing a SOCIALIZE interaction (proximity encounter or dialogue)
- WHEN the interaction is logged
- THEN `EmotionManager.apply_trigger(agent, "socialize")` is called for both agents

#### Scenario: Skill-up triggers proud and curious
- GIVEN an agent whose skill levels up after XP accrual
- WHEN `SkillManager.award_xp()` triggers a level-up
- THEN `EmotionManager.apply_trigger(agent, "skill_up")` is called
