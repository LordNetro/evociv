# Proposal: social-update

## Intent

Agents have conversations and thoughts internally, but there's no visible feedback on the 3D canvas — no speech bubbles, no thought clouds, no social filter in EventLog. This change makes agent social life visible and LLM-driven.

## Scope

### In Scope
- **F1**: LLM response JSON gains `say_to` field; engine converts it to `dialogue` messages and events.
- **F2**: `AgentState` snapshot sends `current_dialogue` + `dialogue_type` to frontend each tick.
- **F3**: Speech bubbles (comic-style) appear above agents in 3D canvas, auto-dismiss.
- **F4**: Thought bubbles (cloud-style) for internal monologue (`think_aloud`).
- **F5**: "Social" filter in EventLog panel shows `dialogue` events in chat style.

### Out of Scope
- Multi-turn conversations (deferred — current messages are one-shot)
- Persistent dialogue history (beyond existing `monologue_history`)
- Player-to-agent chat
- Bubble collision / overlap prevention

## Capabilities

### New Capabilities
- `dialogue-system`: LLM-to-frontend dialogue pipeline — backend message production, snapshot field contract, 3D speech/thought bubble rendering, and social event channel in EventLog.

### Modified Capabilities
- `agent-society`: LLM response format changes (adds `say_to`), new `dialogue` event type, snapshot contract gains dialogue fields.

## Approach

**Event-Driven Minimal**: Reuse the existing LLM response pipeline — `say_to` lives in the same JSON as `think_aloud`. When the engine polls a completed LLM future, it extracts `say_to`, writes to `agent.current_dialogue`, enqueues a `dialogue` SimEvent, and pushes a `Message` into the target agent's `conversation_queue`. The snapshot picks up `current_dialogue` and `dialogue_type` and ships them to the frontend each tick. Speech/thought bubbles render using the same `<HTML>` + CSS approach as `AgentLabel.svelte`. The EventLog adds a "Social" filter that matches `type === "dialogue"`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/ai/orchestrator.py` | Modified | Extract `say_to` from LLM JSON response |
| `backend/app/simulation/agent.py` | Modified | Add `current_dialogue`, `dialogue_type` to Agent |
| `backend/app/simulation/engine.py` | Modified | Process `say_to` in `_poll_llm_responses`, emit dialogue events |
| `backend/app/simulation/conversation.py` | Modified | Handle `dialogue` message type |
| `backend/app/models/schemas.py` | Modified | `AgentState` gains `current_dialogue`, `dialogue_type` |
| `backend/app/simulation/snapshot.py` | Modified | Map new Agent fields to AgentState |
| `frontend/src/lib/canvas3d/` | New | `SpeechBubble.svelte`, `ThoughtBubble.svelte` |
| `frontend/src/lib/canvas3d/AgentLabel.svelte` | Modified | Integrate bubble components |
| `frontend/src/lib/components/EventLog.svelte` | Modified | Add "Social" filter + dialogue styling |
| `frontend/src/lib/stores/simulationStore.svelte.js` | Modified | Pass dialogue fields through |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM doesn't produce valid `say_to` JSON | Low | Fallback: empty string — no crash, no bubble |
| Bubble rendering overlap in 3D | Med | Single bubble per agent, auto-dismiss next tick |
| Dialogue events flood EventLog | Low | Capped at 100 events in store (existing behavior) |

## Rollback Plan

Revert LLM response extraction (`orchestrator.py` + `engine.py`), snapshot fields (`schemas.py` + `snapshot.py`), Agent fields (`agent.py`), and delete `SpeechBubble.svelte` / `ThoughtBubble.svelte`. Revert EventLog filter. No DB migration needed.

## Dependencies

- Existing LLM response pipeline (`RealLLMOrchestrator` / `MockLLMOrchestrator`)
- Existing `<HTML>` Threlte component pattern (proven by `AgentLabel.svelte`)
- Existing `agent-society` spec (F6 covers message queuing)

## Success Criteria

- [ ] LLM JSON with `say_to` produces a visible speech bubble in 3D canvas
- [ ] Agent `think_aloud` renders as thought bubble (cloud style)
- [ ] Bubbles auto-dismiss when dialogue clears or ticks advance
- [ ] EventLog "Social" filter shows only `dialogue` events with chat formatting
- [ ] All existing engine + social tests pass without modification
