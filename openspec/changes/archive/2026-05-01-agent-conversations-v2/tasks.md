# Tasks: Agent Conversations v2

## Phase 1: Core Response Pipeline

- [x] 1.1 Add `sender_name: str` field to `Message` dataclass in `agent.py`; populate it in `_process_say_to()` when enqueuing dialogue messages (F6-R2)
- [x] 1.2 Replace raw dict social context in `prompts.py` with readable text showing ALL messages: sender name, role, message text, and relationship score per F6-R16/F6-R18
- [x] 1.3 Add response guidance paragraph to `JSON_FORMAT_INSTRUCTION` in `prompts.py` directing LLM to respond via `say_to` based on relationship (F6-R15/F6-R13)
- [x] 1.4 Compute real `nearby_agents` in `orchestrator.py build_prompt()` using agent positions (5-tile radius, exclude hostile/different faction) instead of hardcoded `"none"` (F6-R17)
- [x] 1.5 Pass `agents` list from `_fsm_llm_trigger()` to downstream prompt building to enable nearby-agent computation
- [x] 1.6 Consume `dialogue`/`greeting`/`share_knowledge` messages from `conversation_queue` after LLM processing in both `_fsm_llm_waiting()` and `_poll_llm_responses()` in `engine.py`; preserve `trade_proposal` messages (F6-R14/F6-R9)

## Phase 2: Mock & Tests

- [x] 2.1 Make `MockLLMOrchestrator.build_prompt()` read `conversation_queue` and format dialogue/greeting messages into prompt context so mock "sees" the messages
- [x] 2.2 Make `MockLLMOrchestrator.call_async()` respond with `say_to` to the last sender when queue has dialogue messages; fall back to 50% random otherwise
- [x] 2.3 Write test: agent B responds with `say_to` to A when A sends a dialogue message with `FixedMockLLM` (spec F6-R4 scenario)
- [x] 2.4 Write test: dialogue/greeting consumed from sender's queue after LLM processing; `trade_proposal` preserved (spec F6-R14 scenarios)
- [x] 2.5 Write test: `nearby_agents` includes friendly agents within 5 tiles with name/role/distance, shows `"(none)"` when alone (spec F6-R17 scenarios)
- [x] 2.6 Write test: social context includes relationship score for known senders, `"(relationship: neutral)"` for unknown (spec F6-R18 scenarios)

## Phase 3: Knowledge Sharing

- [x] 3.1 Process `share_knowledge` messages in engine tick loop: update `agent.knowledge` from message content and remove from queue (F6-R19)
- [x] 3.2 Emit `knowledge_shared` SimEvent when a `share_knowledge` message is processed
- [x] 3.3 Write test: `share_knowledge` message updates recipient's knowledge and emits correct SimEvent (spec F6-R19 scenarios)
