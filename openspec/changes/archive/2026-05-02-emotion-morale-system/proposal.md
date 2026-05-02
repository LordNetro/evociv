# Proposal: Emotion/Morale System

## Intent

Psychological emotional state for agents that modulates behavior and LLM decisions. Counterpart to Fase 1b Status Effects.

## Scope

### In Scope
- 8 emotions: happy, sad, angry, fearful, calm, hopeful, proud, curious
- EmotionManager: apply/process_tick/modifiers/dominant
- emotions.yaml → EmotionDef model
- Triggers: eat/build, combat win/lose, socialize, faction death/growth, skill_up/discovery
- LLM prompt, Agent.emotions, snapshot + AgentState, tests

### Out of Scope
- Frontend emotion UI — deferred
- Visual indicators (shader/color) — deferred
- LLM-expressed emotion in speech — deferred
- Complex blending (bittersweet) — deferred

## Capabilities

### New Capabilities
- **`emotion-system`**: Emotion definitions, lifecycle (apply/decay/remove), modifier aggregation, trigger-to-delta mapping, cooldown enforcement. Float intensity model (0.0–1.0).

### Modified Capabilities
- **`agent-roles`**: Agent gains `emotions` field. AgentState snapshot extended.
- **`status-effect-system`**: Emotion modifiers compose multiplicatively with status effects. Separate layer, same `get_total_modifiers()`.
- **`combat-system`**: Win triggers proud; loss triggers fearful/sad.
- **`agent-society`**: SOCIALIZE triggers happy/calm. Faction death triggers sad/angry.
- **`skill-system`**: Level-up triggers proud/curious.

## Approach

Mirror StatusEffectManager pattern: static methods, Agent.emotions dict, YAML definitions. Emotions decay toward 0 per tick (configurable). Triggers add delta, capped at 1.0. 5-tick cooldown per emotion/agent prevents spam. `get_total_modifiers()` aggregates across emotions. `get_dominant_emotion()` picks highest for LLM. Formula: `total = skill_mod * status_mod * emotion_mod`.

## Affected Areas

| Area | Change |
|------|--------|
| `configs/definitions/emotions.yaml` | New |
| `backend/definition_models.py` | +EmotionDef |
| `backend/simulation/emotions.py` | New (EmotionManager) |
| `backend/simulation/agent.py` | +Agent.emotions |
| `backend/simulation/actions.py` | +triggers (eat/build) |
| `backend/simulation/combat.py` | +triggers (win/lose) |
| `backend/simulation/conversation.py` | +socialize trigger |
| `backend/simulation/faction.py` | +death/growth triggers |
| `backend/simulation/engine.py` | +process_tick + triggers |
| `backend/simulation/prompts.py` | +emotion context |
| `backend/api/schemas.py` | +AgentState.emotions |
| `backend/api/snapshot.py` | +emotions in snapshot |
| `tests/` | +test_emotions.py |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Modifier math balance | Medium | Start ±10-20%. Tune via YAML, no code change. |
| Trigger spam | Low | 5-tick cooldown per emotion prevents cycling. |
| LLM prompt bloat | Low | Single line: `Emotions: happy(0.7)` |

## Rollback Plan

Revert `agent.py`, delete `emotions.py`, remove trigger calls from actions/combat/conversation/faction/engine, revert prompts.py. Existing tests pass unchanged.

## Dependencies

- Fase 0 (Data-Driven Definitions) — done
- Fase 1a (Skill Progression) — done
- Fase 1b (Status Effects) — done
- Fase 2 (Agent Actions) — done (current branch)

## Success Criteria

- [ ] All existing tests pass (zero regression)
- [ ] EmotionManager unit tests pass (all methods + edge cases)
- [ ] Snapshot includes `emotions` per agent
- [ ] LLM prompt includes emotional context
- [ ] Trigger wiring: eat→calm, combat_win→proud, socialize→happy, faction_death→sad
- [ ] Zero regression in status-effect-system
