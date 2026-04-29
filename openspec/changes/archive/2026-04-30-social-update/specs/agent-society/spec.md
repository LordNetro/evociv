# Delta for agent-society

> Delta spec for change `social-update`. Modifies `openspec/specs/agent-society/spec.md`.

## ADDED Requirements

### Requirement: F6-R9 — LLM `say_to` Response Field

The LLM JSON response format MUST support an optional `say_to` field with structure `{"agent_id": str, "text": str}`. The engine MUST extract this field when polling completed LLM futures: it MUST set `current_dialogue` and `dialogue_type` on the source agent, and enqueue a `Message` with `content={"type": "dialogue", "text": "..."}` in the destination agent's `conversation_queue`.

#### Scenario: LLM produces say_to

- GIVEN an LLM response for agent "Zog" with `"say_to": {"agent_id": "agent_002", "text": "Hello Mila!"}`
- WHEN the engine polls completed LLM futures
- THEN a `Message` with `content={"type": "dialogue", "text": "Hello Mila!"}` is enqueued in the destination agent's queue
- AND the source agent's `current_dialogue` is set to "Hello Mila!" with `dialogue_type="speech"`

#### Scenario: LLM response omits say_to

- GIVEN an LLM response without a `say_to` field
- WHEN the engine processes the response
- THEN no dialogue message is enqueued
- AND the source agent's `current_dialogue` SHOULD be cleared to `None`

### Requirement: F6-R10 — `think_aloud` Maps to `dialogue_type="thought"`

When the engine processes an LLM response that includes `think_aloud`, it MUST set `agent.current_dialogue` to the `think_aloud` text and `agent.dialogue_type` to `"thought"`, in addition to populating the existing `last_thought` field.

#### Scenario: think_aloud triggers thought bubble

- GIVEN an LLM response with `"think_aloud": "I should find water"`
- WHEN the engine processes the response
- THEN `agent.current_dialogue` is "I should find water"
- AND `agent.dialogue_type` is `"thought"`
- AND `agent.last_thought` is also set (existing behavior preserved)

### Requirement: F6-R11 — Dialogue Event Type

The engine MUST emit a `SimEvent` with `type="dialogue"` when processing an LLM response that produces a `say_to` or `think_aloud` with non-null text. The existing `"socialize"` event type for proximity encounters is unchanged.

#### Scenario: Dialogue event emitted for say_to

- GIVEN an LLM response with valid `say_to`
- WHEN the engine processes it
- THEN a `SimEvent` with `type="dialogue"` and description `"{sender} → {receiver}: {text}"` is emitted

#### Scenario: Dialogue event emitted for think_aloud

- GIVEN an LLM response with `think_aloud="I am tired"`
- WHEN the engine processes it
- THEN a `SimEvent` with `type="dialogue"` and description `"{name} thinks: I am tired"` is emitted

### Requirement: F6-R12 — Agent and Snapshot Dialogue Fields

The `Agent` dataclass MUST gain `current_dialogue: str | None` and `dialogue_type: Literal["speech", "thought"] | None`, both defaulting to `None`. The `AgentState` Pydantic model MUST mirror these fields. The snapshot builder MUST map `Agent` dialogue fields to the `AgentState` for every snapshot tick.

#### Scenario: Fresh agent has null dialogue

- GIVEN a newly created Agent
- WHEN inspected
- THEN `current_dialogue` is `None` and `dialogue_type` is `None`

#### Scenario: Snapshot includes dialogue fields

- GIVEN an agent with `current_dialogue="Hello"` and `dialogue_type="speech"`
- WHEN a `WorldSnapshot` is built
- THEN the agent's `AgentState` in `snapshot.agents[agent_id]` includes `current_dialogue="Hello"` and `dialogue_type="speech"`

## MODIFIED Requirements

### Requirement: F6-R7 — Conversation Event Types

All conversation events MUST be recorded as SimEvents. `"socialize"` events cover proximity encounters (unchanged). `"dialogue"` events cover LLM-produced speech and thoughts (new).

(Previously: All conversation events logged exclusively as type `"socialize"`)

#### Scenario: Unchanged — proximity encounter uses socialize

- GIVEN a proximity encounter between two agents
- WHEN the encounter is detected
- THEN a SimEvent with type `"socialize"` and both agent IDs is logged

#### Scenario: New — LLM speech uses dialogue

- GIVEN an LLM response with `say_to`
- WHEN the engine processes it
- THEN a SimEvent with type `"dialogue"` is logged

### Requirement: LLM JSON Format Instruction Updated

The `JSON_FORMAT_INSTRUCTION` in `prompts.py` MUST include the `say_to` field in the JSON schema alongside the existing `think_aloud`.

(Previously: Only `think_aloud` was specified for textual output)

#### Scenario: say_to appears in prompt

- GIVEN the `JSON_FORMAT_INSTRUCTION` template
- WHEN the prompt is rendered
- THEN the JSON format includes `"say_to": {"agent_id": "target_id", "text": "what to say"}` as an optional field
