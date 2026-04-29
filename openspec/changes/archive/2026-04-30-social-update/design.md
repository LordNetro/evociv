# Design: Social Update — Dialogue Bubbles & Social Event Filter

## Technical Approach

Event-driven pipeline reusing existing LLM response flow. `say_to` is extracted at the same point as `think_aloud`, converted to agent dialogue state + message enqueue + SimEvent, shipped to frontend via snapshot, and rendered as CSS speech/thought bubbles with real-time timers. The EventLog adds a `type === "dialogue"` filter.

## Architecture Decisions

### Decision: Where to process `say_to` / `think_aloud`

| Option | Tradeoffs | Decision |
|--------|-----------|----------|
| Only in `_poll_llm_responses` | Runs after FSM; misses futures resolved during agent's own `llm_waiting` FSM step | ✗ |
| Only in `_fsm_llm_waiting` | Misses futures resolved between FSM runs and the poll step | ✗ |
| **Shared helper called from both** | Covers all paths; DRY; single `say_to` processing method | ✓ |

**Rationale**: Both code paths handle completed LLM futures. The shared helper `_process_say_to(agent, response)` eliminates duplication while ensuring every path is covered.

### Decision: Bubble lifecycle and timer management

| Option | Tradeoffs | Decision |
|--------|-----------|----------|
| Manage in `AgentLabel.svelte` local state | Simpler but loses state when component re-creates; hard to sync across all agents | ✗ |
| **Manage in `canvas3dStore` with real-time timers** | Centralized, survives re-renders; `tick(delta)` runs every frame; reactive via `$state` | ✓ |

**Rationale**: `canvas3dStore` already manages per-frame interpolation. Adding `dialogueBubbles: Record<string, { text, type, visibleUntil } | null>` fits the existing pattern. Speech=3s, Thought=5s (real time). Cleared on snapshot update if `current_dialogue` is None, or on timer expiry in `tick(delta)`.

### Decision: EventLog social filter mechanism

| Option | Tradeoffs | Decision |
|--------|-----------|----------|
| Add `"social"` to the existing severity-based `<select>` | Simple; reuses existing component structure | ✓ |

**Rationale**: The `<select>` already filters events. Adding `"social"` as a new option that filters by `type === "dialogue"` is minimal and consistent. Chat-style rendering (`Zog → Mila: text`) applies only to dialogue events.

### Decision: `say_to` message enqueue in target's `conversation_queue`

| Option | Tradeoffs | Decision |
|--------|-----------|----------|
| Skip queue, just show bubble | Bubble is ephemeral; target agent never "hears" the message | ✗ |
| **Enqueue as Message in target's queue** | Consistent with existing `greeting`/`share_knowledge` pattern; target agent sees in social context prompt | ✓ |

**Rationale**: The queue is the existing social input channel. A `Message` with `content={"type": "dialogue", "text": "..."}` means the target agent will read it in their next LLM prompt via `social_context`.

## Data Flow

```
LLM Response
  │
  ├─ think_aloud: "..." ──→ agent.current_dialogue = "..."
  │                          agent.dialogue_type = "thought"
  │                          SimEvent(type="dialogue", desc="Zog thinks: ...")
  │
  └─ say_to: { agent_id, text } ──→ agent.current_dialogue = text
                                     agent.dialogue_type = "speech"
                                     Message(content={type:"dialogue", text})
                                       → target.conversation_queue
                                     SimEvent(type="dialogue", desc="Zog → Mila: text")

Snapshot (every tick):
  AgentState.current_dialogue  →  canvas3dStore.dialogueBubbles[id]
  AgentState.dialogue_type     →  TypeRender: speech (solid) | thought (dotted)

EventLog filter "Social":
  events.filter(e => e.type === "dialogue")  →  "Zog → Mila: ¡Hola!"
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/ai/prompts.py` | Modify | Add `say_to: { agent_id, text } \| null` to `JSON_FORMAT_INSTRUCTION` |
| `backend/app/ai/orchestrator.py` | Modify | Extract `say_to` from LLM JSON in `_call_ollama()`; add to mock response |
| `backend/app/simulation/agent.py` | Modify | Add `current_dialogue: str \| None`, `dialogue_type: str \| None` to `Agent` dataclass |
| `backend/app/simulation/engine.py` | Modify | Add `_process_say_to()` helper; call from `_poll_llm_responses()` and `_fsm_llm_waiting()` |
| `backend/app/models/schemas.py` | Modify | Add `current_dialogue`, `dialogue_type` to `AgentState` Pydantic model |
| `backend/app/simulation/snapshot.py` | Modify | Map new fields in `_build_agent_state()` |
| `frontend/src/lib/canvas3d/canvas3dStore.svelte.ts` | Modify | Add `dialogueBubbles` state, read from snapshot in `updateTargets()`, expire in `tick(delta)` |
| `frontend/src/lib/canvas3d/AgentLabel.svelte` | Modify | Render speech/thought bubble above label; CSS styling |
| `frontend/src/lib/components/EventLog.svelte` | Modify | Add "Social" filter + chat-style dialogue formatting |

## Interfaces / Contracts

### Agent dataclass (new fields)
```python
@dataclass
class Agent:
    # ... existing fields ...
    current_dialogue: str | None = None
    dialogue_type: str | None = None  # "speech" | "thought"
```

### AgentState schema (new fields)
```python
class AgentState(BaseModel):
    # ... existing fields ...
    current_dialogue: str | None = None
    dialogue_type: str | None = None
```

### LLM JSON format (new field in prompt)
```json
{
  "say_to": {"agent_id": "target_id", "text": "Hello Mila!"},
  "think_aloud": "..."
}
// say_to is nullable — omit or null when not speaking to anyone
```

### SimEvent dialogue event
```python
SimEvent(
    type="dialogue",
    description="Zog → Mila: Hello!"  # say_to format
    # OR
    description="Zog thinks: I should find water"  # think_aloud format
)
```

### canvas3dStore dialogue state
```typescript
type DialogueBubble = {
  text: string;
  type: 'speech' | 'thought';
  visibleUntil: number;  // Date.now() + duration_ms
};

// New store property:
dialogueBubbles: Record<string, DialogueBubble | null>;
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `_process_say_to` with valid `say_to` | Mock LLM response; verify `current_dialogue`, `dialogue_type`, queue length, SimEvent emission |
| Unit | `_process_say_to` with `think_aloud` only | Verify `dialogue_type="thought"`, no message enqueued, SimEvent emitted |
| Unit | `_process_say_to` with neither | Verify both fields remain `None`, no event |
| Unit | Snapshot includes dialogue fields | Build AgentState, verify new fields present |
| Unit | `JSON_FORMAT_INSTRUCTION` contains `say_to` | String assertion |
| Integration | End-to-end: mock LLM → snapshot → frontend store | Full tick cycle with mock; verify dialogue data in snapshot |
| Manual | Speech bubble renders in 3D canvas | Visual inspection |
| Manual | Thought bubble renders as cloud style | Visual inspection |
| Manual | Bubble auto-dismisses after timer | Visual + console timing |
| Manual | EventLog "Social" filter works | Visual inspection |

## Migration / Rollout

No migration required. New Agent fields default to `None`, so existing snapshots are backwards-compatible. LLM prompts gain a new optional field — existing models that don't produce `say_to` will simply omit it (fallback to null).

## Open Questions

- None.
