# Delta for agent-society

> Change: **agent-conversations-v2**
> Target: `openspec/specs/agent-society/spec.md` (F6 — Socialization and Conversations)

## ADDED Requirements

### Requirement: F6-R14 — Dialogue Message Consumption

After an LLM response with a `say_to` is fully processed, the engine MUST consume (remove) `dialogue` and `greeting` type messages from the source agent's `conversation_queue` that were provided as context for the LLM prompt. `trade_proposal` messages SHALL NOT be consumed by this mechanism — they have their own processing pipeline via `_process_trade_proposals`.

#### Scenario: Dialogue consumed after LLM response

- GIVEN Agent A has 2 `dialogue` messages and 1 `greeting` in its queue WHEN A's LLM response is processed containing a `say_to` THEN the 2 dialogue and 1 greeting messages are removed from A's queue
- GIVEN an agent has a `trade_proposal` and a `dialogue` message WHEN LLM response is processed THEN only the `dialogue` is consumed; `trade_proposal` remains

### Requirement: F6-R15 — Response Guidance in LLM Instruction

The `JSON_FORMAT_INSTRUCTION` SHALL include guidance directing the LLM to respond to received messages. The `say_to` field description SHALL be updated to mention responding. A new paragraph SHALL be added: "If someone said something to you, respond based on your relationship. Consider their message and your current needs when crafting a reply."

#### Scenario: Response guidance in prompt

- GIVEN an agent with messages in `conversation_queue` WHEN the prompt is built THEN `JSON_FORMAT_INSTRUCTION` includes text instructing the LLM to respond to received messages
- GIVEN an agent with no messages WHEN the prompt is built THEN the response guidance is still present but the LLM may choose not to use `say_to`

### Requirement: F6-R16 — Readable Social Context with Sender Name

The SOCIAL CONTEXT section in the LLM prompt SHALL format each pending message as readable text: `- From {sender_name}: {message_type}: {text}` instead of a raw Python dict. The `Message` dataclass SHALL gain a `sender_name: str` field. The `_process_say_to` method SHALL populate `sender_name` when enqueuing dialogue messages.

#### Scenario: Readable social context

- GIVEN Agent B has a `dialogue` message from Alice with text "Hello!" WHEN B's prompt is built THEN SOCIAL CONTEXT includes `- From Alice: dialogue: Hello!`
- GIVEN Agent B has a `greeting` message from Bob WHEN B's prompt is built THEN SOCIAL CONTEXT includes `- From Bob: greeting: greeted you`

### Requirement: F6-R17 — Real Nearby Agents in Prompts

`RealLLMOrchestrator.build_prompt()` SHALL pass actual nearby friendly agents to `nearby_agents` instead of hardcoding `"none"`. Friendly agents are those within perception radius (5 tiles) who are NOT hostile (different faction). The formatted string SHALL include name, role, and distance.

#### Scenario: Nearby agents in prompt

- GIVEN Alice (gatherer) at (5,5) and Bob (builder) at (7,5) WHEN RealLLMOrchestrator builds Alice's prompt THEN NEARBY AGENTS includes "Bob (builder) at distance 2"
- GIVEN Alice is alone (no agents within 5 tiles) WHEN her prompt is built THEN NEARBY AGENTS shows "(none)"

### Requirement: F6-R18 — Relationship Scores in Social Context

The SOCIAL CONTEXT SHALL include the relationship score with the message sender when the agent has an existing relationship entry. Format: `- From {name}: {type} (relationship: {score:.1f})`. If no relationship exists, append `(relationship: neutral)`.

#### Scenario: Relationship score in social context

- GIVEN Agent A has relationship score 0.8 with Agent B WHEN A's prompt shows B's message THEN `(relationship: 0.8)` appears in the social context line
- GIVEN Agent A has no relationship with Agent C WHEN A's prompt shows C's message THEN `(relationship: neutral)` appears

### Requirement: F6-R19 — Knowledge Sharing Processing in Tick Loop

The engine SHALL process `share_knowledge` messages from agents' `conversation_queue` each tick, before trade proposals. When found, the receiving agent's `knowledge` store SHALL be updated with the shared subtype and properties, the message SHALL be consumed (removed), and a `knowledge_shared` SimEvent SHALL be emitted.

#### Scenario: Knowledge share processing

- GIVEN Agent B has a `share_knowledge` message for POISONOUS_BERRY with `{"is_poisonous": true}` WHEN the engine processes the queue THEN B's `knowledge["POISONOUS_BERRY"]["is_poisonous"]` is True AND the message is removed from B's queue
- GIVEN a `share_knowledge` message is processed WHEN the event queue is drained THEN a SimEvent with type `knowledge_shared` is present

## MODIFIED Requirements

### Requirement: F6-R2 — Message Structure

Each agent MUST have a `conversation_queue: list[Message]` (FIFO, max 50 messages). Each `Message` MUST contain: `sender_id` (str), `sender_name` (str), `content` (structured dict), and `tick` (int). The `sender_name` field SHALL hold the sending agent's human-readable name.
(Previously: Message had only sender_id, content, tick — no sender_name)

#### Scenario: Message dataclass

- GIVEN a Message created with `sender_id="a1"`, `sender_name="Alice"`, `content={}` WHEN accessed THEN all fields are present and correct

### Requirement: F6-R4 — Message Processing in LLM Context

On each tick, an agent in IDLE state with non-empty `conversation_queue` MUST process the next message in its LLM prompt. The LLM decides how to respond (reply, share knowledge, ignore, propose trade, etc.). After the LLM produces a response, consumed `dialogue` and `greeting` messages MUST be removed from the queue. The prompt MUST include the response guidance (F6-R15) and formatted social context with sender names (F6-R16).
(Previously: LLM received raw unread count + latest dict. No guidance to respond. Messages never consumed.)

#### Scenario: LLM responds to incoming dialogue

- GIVEN Agent B has a `dialogue` message from Alice ("Hello!") WHEN B enters `llm_trigger` state THEN the prompt includes the message and instructs B to respond
- GIVEN B's LLM response includes `say_to` to Alice WHEN the response is processed THEN the consumed dialogue message is removed from B's queue

### Requirement: F6-R9 — say_to Response Pipeline

The LLM JSON response format MUST support an optional `say_to` field with structure `{"agent_id": str, "text": str}`. The engine MUST extract this field when polling completed LLM futures: it MUST set `current_dialogue` and `dialogue_type` on the source agent, and enqueue a `Message` with `sender_name`, `sender_id`, and `content={"type": "dialogue", "text": "..."}` in the destination agent's `conversation_queue`. After enqueuing, the engine MUST consume the handled dialogue/greeting messages from the source agent's queue.
(Previously: say_to was delivered but source queue was never consumed. sender_name was not included in the enqueued Message.)

#### Scenario: say_to with queue consumption

- GIVEN Agent A's LLM response has `say_to: {agent_id: "B", text: "Hi!"}` WHEN the engine processes it THEN a Message with `sender_name=A.name` and `content.type="dialogue"` is enqueued in B's queue AND A's dialogue/greeting messages are consumed from A's queue

- GIVEN an LLM response without `say_to` WHEN processed THEN no dialogue message is enqueued AND the source agent's `current_dialogue` is cleared to `None` AND the consumed messages are still removed from queue

### Requirement: F6-R13 — JSON Format Includes say_to and Response Guidance

The `JSON_FORMAT_INSTRUCTION` in the LLM prompt MUST include the `say_to` field in the JSON schema alongside `think_aloud`, AND MUST include additional guidance text instructing the LLM to respond to received messages. The guidance text SHOULD mention considering the relationship with the sender.
(Previously: Only the `say_to` field definition was included — no guidance on when or how to use it.)

#### Scenario: Prompt includes response guidance

- GIVEN the `JSON_FORMAT_INSTRUCTION` template WHEN rendered THEN it includes both the `say_to` field definition AND a paragraph guiding the LLM to respond to received messages
