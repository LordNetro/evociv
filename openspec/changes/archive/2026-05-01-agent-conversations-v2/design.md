# Design: Agent Conversations v2

## Technical Approach

Three-phase pipeline fix to make agents actually respond to each other: (1) format social context as readable text with response guidance in the LLM prompt, (2) consume dialogue/greeting/share_knowledge messages after LLM processing so queues drain, (3) fix MockLLM to read conversation_queue for deterministic testable responses. Knowledge sharing processed as a bonus in the tick loop. Spec: `dialogue-system` (backfill the server-side pipeline the spec assumes exists).

## Architecture Decisions

### Decision 1: Ephemeral Message Consumption

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Read-flag on `Message` | Intrusive, new field | ❌ |
| Filter removal after LLM | Simple, zero new state | ✅ |
| Pop-and-process | Breaks if multiple msg types coexist | ❌ |

**Rationale**: Dialogue/greeting/share_knowledge are ephemeral — once the LLM processes them they have no further value. Filtering by `type` after LLM completion (`_fsm_llm_waiting` and `_poll_llm_responses`) keeps the queue clean without adding state. Trade proposals keep their own lifecycle in `_process_trade_proposals`.

### Decision 2: Queue-Aware MockLLM

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Random say_to (current) | No testability | ❌ |
| Respond to last sender | Deterministic, testable | ✅ |
| Respond to all senders | Overwrites multiple times | ❌ |

**Rationale**: MockLLM must mirror real LLM behavior for deterministic tests. Responding to the last sender in the queue creates predictable conversations: A says "Hi" → B sees msg in queue → B responds to A. Makes `test_dialogue.py` assertions reliable.

### Decision 3: Full Queue Social Context

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Latest msg only (current) | LLM misses full context | ❌ |
| ALL messages, readable text | LLM sees full picture | ✅ |
| Count + latest | Good but still incomplete | ❌ |

**Rationale**: LLM needs all pending interactions to decide tone per sender. Format as readable text with sender name, role, message text, and relationship score. Raw Python dicts (`latest.content`) are useless to LLMs.

## Data Flow

```
[Agent A LLM response]
  │  say_to: {"agent_id": "B", "text": "Hello!"}
  ▼
_process_say_to()
  ├── enqueue Message(type="dialogue") in B's conversation_queue
  ├── set A.current_dialogue, A.dialogue_type
  └── push dialogue SimEvent

[B's next LLM prompt]
  │  SOCIAL CONTEXT includes ALL unread messages
  │  e.g. "- Message from A (gatherer): \"Hello!\" [rel: +0.15]"
  ▼
JSON_FORMAT_INSTRUCTION guides B to respond via say_to
  │
  ▼
[B's response] → say_to back to A
  │
  ▼
_process_say_to() → enqueue in A's queue
  │
  ▼
Consume: filter out type in (dialogue, greeting, share_knowledge)
from B's queue

[Knowledge flow - tick loop]
ConversationManager.detect_encounters()
  → enqueue Message(type="share_knowledge", subtype="berries", ...)
  → tick loop iterates agents → for each share_knowledge msg:
    → agent.knowledge[subtype].update(properties)
    → remove msg from queue
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/ai/prompts.py` | Modify | Readable social context format (all messages), response guidance in `JSON_FORMAT_INSTRUCTION`, relationship scores | |`backend/app/ai/orchestrator.py` | Modify | Compute `nearby_agents` from agent positions instead of hardcoded `"none"`, pass `agents` list from `_fsm_llm_trigger` |
| `backend/app/simulation/engine.py` | Modify | Consume dialogue/greeting/share_knowledge after LLM in `_fsm_llm_waiting` & `_poll_llm_responses`; tick loop processes share_knowledge messages |
| `backend/app/simulation/agent.py` | Modify | `MockLLMOrchestrator` reads `conversation_queue`, responds to last sender with relevant text |
| `backend/tests/test_dialogue.py` | Modify | Add response pipeline, queue consumption, MockLLM queue-aware tests |

## Interfaces / Contracts

No new interfaces. `MockLLMOrchestrator.call_async()` behavior changes:

- If agent has dialogue/greeting/share_knowledge messages in queue → respond to **last sender** with relevant text
- If queue is empty → current random say_to behavior (50% chance)

Social context format:
```
SOCIAL CONTEXT:
- Message from Zog (gatherer): "Hey there!" [relationship: +0.15]
- Message from Mila (builder): "I found berries!" [relationship: +0.30]
```
When no messages: `SOCIAL CONTEXT:\n- No pending messages`

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Social context formatting | Assert formatted string contains sender name, role, text, relationship score |
| Unit | Queue consumption | After LLM processes say_to, assert dialogue/greeting removed, trade_proposal kept |
| Unit | MockLLM queue-aware | Enqueue message → call call_async → assert say_to targets correct sender |
| Unit | nearby_agents fix | Agents within 5 tiles → `nearby_agents` != `"none"` |
| Unit | Knowledge sharing | share_knowledge msg in queue → after tick → `agent.knowledge` updated |

## Migration / Rollout

No migration required. Queue consumption is additive — old messages drain on first tick after deploy. No feature flags.

## Open Questions

- [ ] Should we consume sent messages from the sender's queue too? (Currently sender keeps its own sent messages — only useful for the target. Proposed: no self-consume.)
