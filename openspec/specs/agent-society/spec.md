# Spec: agent-society

> Consolidated spec — synced from delta `openspec/changes/agent-society/specs/agent-society/spec.md`
> Archive: `openspec/changes/archive/agent-society/archive-report.md`
> Delta applied: `openspec/changes/agent-conversations-v2/specs/agent-society/spec.md` (2026-05-01)

## Capabilities

### capability: agent-society
**Depends on**: simulation-engine

Extends the core simulation with a full social simulation layer: relationships, conversations, trade, childhood dependency, factions, limited perception (knowledge), LLM action-feedback, and colony-level UI.

#### Requirements

**F1 — LLM-Triggered Action Feedback**

| # | Requirement | Strength |
|---|-------------|----------|
| F1-R1 | The system MUST capture the `ActionResult` from each completed action (success/failure, stat deltas, inventory deltas, events produced) and pass it as structured context to the LLM on the agent's next `decide_next_action()` call. | MUST |
| F1-R2 | The system MUST include the `ActionResult` context as a dedicated field in the LLM prompt (e.g., `last_action_result`) separate from the agent's current stats and world state. | MUST |
| F1-R3 | If the agent has no prior action (first tick after spawn), the `last_action_result` field MUST be `null`/`None` instead of producing an error. | MUST |
| F1-R4 | If the LLM call times out or fails, the agent MUST fall back to instinct behavior (find nearest food/water) and the pending `ActionResult` context MUST be discarded (not accumulated across ticks). | MUST |
| F1-R5 | The `ActionResult` context MUST include the `ActionType` that was executed, the `success` boolean, and a summary of stat changes (e.g., `hunger:-30`, `wood:+5`). | MUST |

**F2 — Limited Perception / Knowledge**

| # | Requirement | Strength |
|---|-------------|----------|
| F2-R1 | Resources on the world grid MUST have a `subtype` field (e.g., `POISONOUS_BERRY`, `SAFE_BERRY`, `OAK_TREE`, `PINE_TREE`) in addition to the base `resource_type` (e.g., `BERRY`, `WOOD`). | MUST |
| F2-R2 | Each resource subtype MUST define a set of `hidden_properties: dict[str, Any]` that are NOT visible to agents through vision/perception alone (e.g., `{"is_poisonous": true}` for `POISONOUS_BERRY`). | MUST |
| F2-R3 | Agents MUST NOT receive `hidden_properties` in their world state snapshot — only the base `resource_type` and `subtype` name are visible. | MUST |
| F2-R4 | When an agent consumes a resource (EAT action), the hidden properties of that resource's subtype MUST be revealed to the agent and stored in the agent's individual `knowledge` store. | MUST |
| F2-R5 | Each agent MUST have an independent `knowledge: dict[str, dict[str, Any]]` store mapping `subtype_name -> {property: value}`. Agent A learning that `POISONOUS_BERRY` is poisonous does NOT mean Agent B knows it. | MUST |
| F2-R6 | The agent's LLM prompt MUST include the agent's known knowledge as context when making decisions about resources (e.g., "You know that POISONOUS_BERRY is poisonous"). | MUST |
| F2-R7 | Knowledge discovered by one agent MUST be shareable with another agent via the conversation system (F6). Shared knowledge is added to the receiving agent's `knowledge` store. | MUST |

**F3 — Childhood and Parental Care**

| # | Requirement | Strength |
|---|-------------|----------|
| F3-R1 | Newborn agents MUST be created with `is_child: bool = True` and `parent_id: str` pointing to their parent agent's ID. | MUST |
| F3-R2 | Child agents MUST NOT be able to execute `EAT` or `DRINK` actions independently. If a child's FSM attempts to eat/drink, it MUST be blocked. | MUST |
| F3-R3 | A new `FEED_CHILD` action type MUST be added. The caregiver executes `FEED_CHILD(child_id)` which transfers resources from the caregiver's inventory to satisfy the child's hunger/thirst. | MUST |
| F3-R4 | A child agent MUST spawn adjacent to its parent (Manhattan distance ≤ 2). | MUST |
| F3-R5 | The parent/caregiver's FSM MUST prioritize `FEED_CHILD` when the child's hunger or thirst exceeds a critical threshold (e.g., > 70), overriding the caregiver's own needs. | MUST |
| F3-R6 | Child agents' initial stats (strength, intelligence, sociability) MUST be derived from the parent's stats with a random offset (e.g., `child.str = parent.str ± random(0, 15)`), clamped to [0, 100]. | MUST |
| F3-R7 | Each child agent MUST have a `maturity_age: int` (in ticks). When `tick_count >= maturity_age`, `is_child` MUST be set to `False`, and `parent_id` MAY be cleared. After maturity, the agent gains full autonomy. | MUST |
| F3-R8 | If a caregiver dies before the child matures, any nearby adult agent within interaction radius MAY adopt the child (auto-assigned via proximity). If no adult is within radius, the child's stats decay fatally. | MUST |

**F4 — Factions**

| # | Requirement | Strength |
|---|-------------|----------|
| F4-R1 | A new `Faction` data model MUST exist with fields: `id` (str), `name` (str), `color` (str, hex), `member_ids` (list[str]), `shared_resources` (dict[str, int]). | MUST |
| F4-R2 | The `Agent` dataclass MUST gain an optional `faction_id: str | None` field. | MUST |
| F4-R3 | Faction CRUD MUST be supported: create, delete, join (add member), leave (remove member), and list all factions. | MUST |
| F4-R4 | The WebSocket snapshot MUST include faction information: each faction's id, name, color, member count, and total shared resources. | MUST |
| F4-R5 | The frontend canvas MUST render agents with their faction's `color` as a border or overlay when the agent belongs to a faction. | MUST |
| F4-R6 | When an agent's FSM evaluates trade requests (F5), same-faction agents MUST be preferred (higher acceptance probability in the LLM prompt context). | MUST |
| F4-R7 | When a faction member dies, their personal inventory MUST be transferred to the faction's `shared_resources`. Additionally, all faction members MUST receive `sad` and `angry` emotion triggers via `EmotionManager.apply_trigger(survivor, "on_faction_death")`. | MUST |

**F5 — Trading**

| # | Requirement | Strength |
|---|-------------|----------|
| F5-R1 | A new `TRADE` action type MUST be added to `ActionType` enum and registered in the action `REGISTRY`. | MUST |
| F5-R2 | `TRADE` MUST be initiated by one agent (the proposer) targeting another agent within interaction radius (distance ≤ 3 tiles). The proposer specifies `offer: dict[str, int]` (what they give) and `request: dict[str, int]` (what they want). | MUST |
| F5-R3 | The target agent's LLM MUST receive the trade proposal as context and decide to accept or reject based on the target's current needs, inventory, and relationship with the proposer. | MUST |
| F5-R4 | If the target accepts, resources MUST be transferred atomically: proposer's inventory debited for `offer`, target's inventory debited for `request`, then both credited with the opposite side. If either side lacks sufficient resources, the trade MUST fail. | MUST |
| F5-R5 | If the target rejects (or the LLM call times out), neither agent's inventory is modified. The rejection MUST be logged as a SimEvent. | MUST |
| F5-R6 | A successful trade MUST increment the `interaction_count` between both agents (for F8 relationship tracking). | MUST |

**F6 — Socialization and Conversations**

> Synced from delta `openspec/changes/agent-conversations-v2/specs/agent-society/spec.md`

| # | Requirement | Strength |
|---|-------------|----------|
| F6-R1 | A new `SOCIALIZE` action type MUST be added. The action is triggered automatically when two agents are within interaction radius (≤ 3 tiles). | MUST |
| F6-R2 | Each agent MUST have a `conversation_queue: list[Message]` (FIFO, max 50 messages). Each `Message` MUST contain: `sender_id` (str), `sender_name` (str), `content` (structured dict), and `tick` (int). The `sender_name` field SHALL hold the sending agent's human-readable name. | MUST |
| F6-R3 | When a proximity encounter is detected, a `Message` is enqueued in both agents' queues. The message content describes the encounter (e.g., `{"type": "greeting", "agent_name": "Alice"}`). | MUST |
| F6-R4 | On each tick, an agent in IDLE state with non-empty `conversation_queue` MUST process the next message in its LLM prompt. The LLM decides how to respond (reply, share knowledge, ignore, propose trade, etc.). After the LLM produces a response, consumed `dialogue` and `greeting` messages MUST be removed from the queue. The prompt MUST include the response guidance (F6-R15) and formatted social context with sender names (F6-R16). | MUST |
| F6-R5 | Agents MAY share knowledge from their `knowledge` store (F2) through conversation. When an agent shares a known property, the receiving agent's `knowledge` store MUST be updated. | MUST |
| F6-R6 | Each successful conversation interaction MUST increment the `interaction_count` for both participants, feeding into F8's relationship system. | MUST |
| F6-R7 | All conversation events MUST be recorded as SimEvents. `"socialize"` events cover proximity encounters (unchanged). `"dialogue"` events cover LLM-produced speech and thoughts (new). Additionally, successful SOCIALIZE interactions MUST trigger `happy` and `calm` emotion events for both participants via `EmotionManager.apply_trigger(agent, "on_socialize")`. | MUST |
| F6-R8 | To prevent tick-loop spam, a maximum of 5 conversation pairs per tick MUST be processed. Additional pending pairs are deferred to the next tick. | MUST |
| F6-R9 | The LLM JSON response format MUST support an optional `say_to` field with structure `{"agent_id": str, "text": str}`. The engine MUST extract this field when polling completed LLM futures: it MUST set `current_dialogue` and `dialogue_type` on the source agent, and enqueue a `Message` with `sender_name`, `sender_id`, and `content={"type": "dialogue", "text": "..."}` in the destination agent's `conversation_queue`. After enqueuing, the engine MUST consume the handled dialogue/greeting messages from the source agent's queue. | MUST |
| F6-R10 | When the engine processes an LLM response that includes `think_aloud`, it MUST set `agent.current_dialogue` to the `think_aloud` text and `agent.dialogue_type` to `"thought"`, in addition to populating the existing `last_thought` field. | MUST |
| F6-R11 | The engine MUST emit a `SimEvent` with `type="dialogue"` when processing an LLM response that produces a `say_to` or `think_aloud` with non-null text. The existing `"socialize"` event type for proximity encounters is unchanged. | MUST |
| F6-R12 | The `Agent` dataclass MUST gain `current_dialogue: str | None` and `dialogue_type: Literal["speech", "thought"] | None`, both defaulting to `None`. The `AgentState` Pydantic model MUST mirror these fields. The snapshot builder MUST map `Agent` dialogue fields to the `AgentState` for every snapshot tick. | MUST |
| F6-R13 | The `JSON_FORMAT_INSTRUCTION` in the LLM prompt MUST include the `say_to` field in the JSON schema alongside `think_aloud`, AND MUST include additional guidance text instructing the LLM to respond to received messages. The guidance text SHOULD mention considering the relationship with the sender. | MUST |
| F6-R14 | After an LLM response with a `say_to` is fully processed, the engine MUST consume (remove) `dialogue` and `greeting` type messages from the source agent's `conversation_queue` that were provided as context for the LLM prompt. `trade_proposal` messages SHALL NOT be consumed by this mechanism — they have their own processing pipeline via `_process_trade_proposals`. | MUST |
| F6-R15 | The `JSON_FORMAT_INSTRUCTION` SHALL include guidance directing the LLM to respond to received messages. The `say_to` field description SHALL be updated to mention responding. A new paragraph SHALL be added: "If someone said something to you, respond based on your relationship. Consider their message and your current needs when crafting a reply." | MUST |
| F6-R16 | The SOCIAL CONTEXT section in the LLM prompt SHALL format each pending message as readable text: `- From {sender_name}: {message_type}: {text}` instead of a raw Python dict. The `Message` dataclass SHALL have a `sender_name: str` field. The `_process_say_to` method SHALL populate `sender_name` when enqueuing dialogue messages. | MUST |
| F6-R17 | `RealLLMOrchestrator.build_prompt()` SHALL pass actual nearby friendly agents to `nearby_agents` instead of hardcoding `"none"`. Friendly agents are those within perception radius (5 tiles) who are NOT hostile (different faction). The formatted string SHALL include name, role, and distance. | MUST |
| F6-R18 | The SOCIAL CONTEXT SHALL include the relationship score with the message sender when the agent has an existing relationship entry. Format: `- From {name}: {type} (relationship: {score:.1f})`. If no relationship exists, append `(relationship: neutral)`. | MUST |
| F6-R19 | The engine SHALL process `share_knowledge` messages from agents' `conversation_queue` each tick, before trade proposals. When found, the receiving agent's `knowledge` store SHALL be updated with the shared subtype and properties, the message SHALL be consumed (removed), and a `knowledge_shared` SimEvent SHALL be emitted. | MUST |

**F7 — Colony Information Panel**

| # | Requirement | Strength |
|---|-------------|----------|
| F7-R1 | A new REST endpoint `GET /api/colony` MUST return colony-level statistics: total population, births count (agents spawned this session), deaths count, alive/dead ratio, distribution by role, sex, age groups, total resources across all agents, total structures, structures by type, total equipment (weapons/armor held by agents), and active factions list. | MUST |
| F7-R2 | The WebSocket snapshot MUST be extended with a `colony_stats` field containing a subset of frequently-changing metrics: population, births, deaths, total resources, total_structures, structures_by_type, and total_equipment. | MUST |
| F7-R3 | A new `ColonyInfo.svelte` component MUST be created in the frontend that displays: population (total, births, deaths), demographic breakdown (role/age distribution as simple bars or table), total resources, and active factions. | MUST |
| F7-R4 | The ColonyInfo panel MUST auto-refresh from the WebSocket snapshot data (no polling). The REST endpoint serves as the initial load and for detailed data not in the snapshot. | MUST |
| F7-R5 | The frontend HUD MUST show key colony metrics as minimal widgets: population count, births this session, deaths this session. | MUST |

**F8 — Relationship-Based Reproduction**

| # | Requirement | Strength |
|---|-------------|----------|
| F8-R1 | The `Agent` dataclass MUST gain a `relationships: dict[str, RelationshipData]` field where the key is another agent's ID. `RelationshipData` contains: `interaction_count` (int), `last_interaction_tick` (int), and `score` (float, -1.0 to 1.0). | MUST |
| F8-R2 | Every interaction (trade, conversation, shared-resource use) increments `interaction_count` for both agents and updates `score` based on interaction type (positive for trade/gift, neutral for conversation, negative for theft/conflict). | MUST |
| F8-R3 | The `REPRODUCE` action MUST be gated by a configurable `INTERACTION_THRESHOLD` (default: 5). The agent's `_find_reproduction_partner()` method MUST only consider agents with `interaction_count >= INTERACTION_THRESHOLD`. | MUST |
| F8-R4 | Relationship scores MUST decay over time: if `current_tick - last_interaction_tick > DECAY_INTERVAL` (e.g., 100 ticks), `interaction_count` decrements by 1 each additional tick (minimum 0). | MUST |
| F8-R5 | The AgentInspector panel in the frontend MUST display a "Relationships" section listing each known agent's name, interaction count, and relationship score. | MUST |
| F8-R6 | Relationship data MUST be included in the WebSocket snapshot per-agent so the frontend can render it. | MUST |
| F8-R7 | Relationship-aware reproduction MUST replace the current unconditional reproduction logic. Agents with zero interactions MUST NOT be able to reproduce. | MUST |

**F9 — New ActionTypes in Agent Society**

| # | Requirement | Strength |
|---|-------------|----------|
| F9-R1 | The `ActionType` enum SHALL be extended with 10 new values: MINE, HUNT, FISH, FARM, CRAFT, BUILD, ATTACK, GUARD, EXPLORE, HEAL. These SHALL be registered in `REGISTRY`, `ACTION_EMOJIS`, and `get_action_duration()`. | MUST |
| F9-R2 | All 20 ActionTypes (10 original + 10 new) SHALL have corresponding handler functions registered in the `REGISTRY` dict. | MUST |

**F10 — Agent Equipment Fields**

| # | Requirement | Strength |
|---|-------------|----------|
| F10-R1 | The `Agent` dataclass SHALL gain an `equipment: dict[str, str]` field with keys `weapon`, `armor`, `tool`. Default values: `{"weapon": "fist", "armor": "none", "tool": "none"}`. | MUST |
| F10-R2 | The `equipment` field SHALL be serialized in the `AgentState` Pydantic model and included in the WebSocket snapshot. | MUST |

**F11 — Role-Specific Behavioral Context in LLM Prompts**

| # | Requirement | Strength |
|---|-------------|----------|
| F11-R1 | The LLM prompt builder SHALL include role-specific behavioral guidance. Each role's description, allowed actions, and priority intent SHALL appear in both the system prompt and the state prompt context. | MUST |
| F11-R2 | The `JSON_FORMAT_INSTRUCTION` SHALL include all 10 new actions in the steps action enum alongside existing actions. | MUST |

**F12 — Structure Awareness in LLM Prompts**

| # | Requirement | Strength |
|---|-------------|----------|
| F12-R1 | The LLM prompt SHALL include context about nearby structures: their type, position, owner, and health. This context SHALL appear in the state prompt template alongside nearby resources. | MUST |

**F13 — Equipment in AgentState Schema**

| # | Requirement | Strength |
|---|-------------|----------|
| F13-R1 | The `AgentState` Pydantic model SHALL gain an `equipment: dict[str, str]` field mirroring the `Agent.equipment` field. | MUST |

**F14 — Structures in WorldSnapshot Schema**

| # | Requirement | Strength |
|---|-------------|----------|
| F14-R1 | The `WorldSnapshot` Pydantic model SHALL gain an optional `structures: list[dict]` field. Each structure dict SHALL contain: `id`, `type`, `position`, `owner_id`, `health`, `max_health`, and `properties`. | MUST |

#### Scenarios

**F1 — LLM-Triggered Action Feedback**

- GIVEN an agent that just completed a `CHOP` action with `ActionResult(success=True, stat_deltas={"energy": -10}, inventory_deltas={"wood": +3})` WHEN the agent enters `LLM_TRIGGER` state THEN the LLM prompt includes `last_action_result: {type: "CHOP", success: true, effects: "energy:-10, wood:+3"}`
- GIVEN a newly spawned agent with no prior action WHEN it enters `LLM_TRIGGER` for the first time THEN `last_action_result` is `null`/`None`
- GIVEN an agent whose LLM call fails (timeout) WHEN FSM processes the failed future THEN the agent falls back to instinct behavior and `last_action_result` is NOT accumulated for the next LLM call
- GIVEN an agent that completed a `DRINK` action (thirst satisfied) WHEN LLM prompt is built THEN the `last_action_result` includes the thirst change and the resource tile consumed

**F2 — Limited Perception / Knowledge**

- GIVEN a world with `POISONOUS_BERRY` subtype (hidden: `{"is_poisonous": true}`) WHEN an agent receives the world snapshot THEN the tile shows `resource_type="BERRY", subtype="POISONOUS_BERRY"` but does NOT include `is_poisonous`
- GIVEN an agent consumes a `POISONOUS_BERRY` (EAT action) WHEN the action completes THEN the agent's `knowledge["POISONOUS_BERRY"]["is_poisonous"]` is `True`, and the agent loses health
- GIVEN an agent with `knowledge={"POISONOUS_BERRY": {"is_poisonous": True}}` WHEN the LLM is queried about what to eat THEN the knowledge is included as context: "You know POISONOUS_BERRY is poisonous"
- GIVEN Agent A knows `POISONOUS_BERRY` is poisonous and Agent B does NOT WHEN Agent A shares this knowledge via conversation THEN Agent B's `knowledge["POISONOUS_BERRY"]["is_poisonous"]` is set to `True`

**F3 — Childhood and Parental Care**

- GIVEN a newborn agent WHEN created THEN `is_child=True`, `parent_id` is set, and the agent spawns on a tile adjacent to the parent
- GIVEN a child agent with hunger=90 (critical) WHEN its FSM ticks THEN the action is NOT EAT/DRINK — the child waits; the parent's FSM triggers `FEED_CHILD` instead
- GIVEN a parent executes `FEED_CHILD(child_id)` with `inventory={"berry": 5}` WHEN the action completes THEN the child's hunger decreases by 30 and the parent's inventory decreases by 1 berry
- GIVEN child agent with parent stats `strength=70, intelligence=50, sociability=30` WHEN the child is spawned THEN its stats are within `[55-85], [35-65], [15-45]` respectively (parent ±15)
- GIVEN a child agent with `maturity_age=500` WHEN `tick_count >= 500` THEN `is_child=False` and the agent can independently eat/drink
- GIVEN a caregiver agent dies while a child is still dependent WHEN the tick loop checks for adopters THEN a nearby adult within 3 tiles is assigned as new caregiver; if none exists, the child's health decays each tick until death

**F4 — Factions**

- GIVEN a faction with `color="#FF0000"` WHEN a member agent is rendered in the frontend canvas THEN the agent has a red border/overlay
- GIVEN a faction member dies WHEN death is processed THEN the agent's inventory is transferred to the faction's `shared_resources`
- GIVEN a faction member dies WHEN death is processed THEN `EmotionManager.apply_trigger(survivor, "on_faction_death")` is called for each surviving member
- GIVEN two agents in the same faction WHEN one proposes a trade THEN the LLM prompt includes context that they are faction allies, increasing acceptance likelihood
- GIVEN a faction with 3 members WHEN queried via GET /api/factions THEN the response includes id, name, color, member_count=3, and shared_resources

**F5 — Trading**

- GIVEN Agent A at (10,10) and Agent B at (11,10) within interaction radius WHEN Agent A initiates TRADE with offer={"wood": 3} and request={"berry": 5} THEN the trade proposal is added to Agent B's conversation queue
- GIVEN Agent B receives a trade proposal and its LLM accepts WHEN the trade is processed THEN Agent A loses 3 wood, Agent B loses 5 berry, Agent A gains 5 berry, Agent B gains 3 wood (atomic swap)
- GIVEN Agent A has offer={"wood": 10} but only has 3 wood in inventory WHEN the trade is evaluated THEN the action fails with `success=False` and neither inventory is modified
- GIVEN a successful trade between Agent A and Agent B WHEN the trade completes THEN both agents' `interaction_count` increments by 1

**F6 — Socialization and Conversations**

- GIVEN two agents within distance ≤ 3 tiles WHEN the proximity check runs THEN a `Message` is enqueued in both agents' `conversation_queue` AND `EmotionManager.apply_trigger(a1, "on_socialize")` and `EmotionManager.apply_trigger(a2, "on_socialize")` are called
- GIVEN an agent in IDLE state with `conversation_queue` containing 3 messages WHEN the FSM ticks THEN the agent processes the oldest message, the LLM receives the message context and produces a response plan, and consumed messages are removed from the queue afterwards
- GIVEN Agent A shares knowledge about `POISONOUS_BERRY` via a conversation message WHEN Agent B processes the message THEN Agent B's `knowledge` store is updated with the shared information
- GIVEN a conversation event WHEN it occurs THEN a SimEvent with type `"socialize"` is logged containing both agent IDs and message summary
- GIVEN more than 5 conversation pairs are pending in a single tick WHEN the tick processes social interactions THEN only 5 pairs are processed and the remainder are deferred to the next tick
- GIVEN an LLM response for agent "Zog" with `"say_to": {"agent_id": "agent_002", "text": "Hello Mila!"}` WHEN the engine polls completed LLM futures THEN a `Message` with `sender_name`, `sender_id`, and `content={"type": "dialogue", "text": "Hello Mila!"}` is enqueued in the destination agent's queue AND the source agent's `current_dialogue` is set to "Hello Mila!" with `dialogue_type="speech"` AND the source agent's dialogue/greeting messages are consumed from its queue
- GIVEN an LLM response without a `say_to` field WHEN the engine processes the response THEN no dialogue message is enqueued AND the source agent's `current_dialogue` SHOULD be cleared to `None` AND dialogue/greeting messages are still consumed from the queue
- GIVEN an LLM response with `"think_aloud": "I should find water"` WHEN the engine processes the response THEN `agent.current_dialogue` is "I should find water" AND `agent.dialogue_type` is `"thought"` AND `agent.last_thought` is also set
- GIVEN an LLM response with valid `say_to` WHEN the engine processes it THEN a `SimEvent` with `type="dialogue"` and description `"{sender} → {receiver}: {text}"` is emitted
- GIVEN an LLM response with `think_aloud="I am tired"` WHEN the engine processes it THEN a `SimEvent` with `type="dialogue"` and description `"{name} thinks: I am tired"` is emitted
- GIVEN a newly created Agent WHEN inspected THEN `current_dialogue` is `None` and `dialogue_type` is `None`
- GIVEN an agent with `current_dialogue="Hello"` and `dialogue_type="speech"` WHEN a `WorldSnapshot` is built THEN the agent's `AgentState` in `snapshot.agents[agent_id]` includes `current_dialogue="Hello"` and `dialogue_type="speech"`
- GIVEN the `JSON_FORMAT_INSTRUCTION` template WHEN the prompt is rendered THEN the JSON format includes `"say_to": {"agent_id": "target_id", "text": "what to say"}` as an optional field AND a guidance paragraph instructing the LLM to respond to received messages
- GIVEN a `Message` created with `sender_id="a1"`, `sender_name="Alice"`, `content={}` WHEN accessed THEN all fields are present and correct
- GIVEN Agent B has a `dialogue` message from Alice ("Hello!") WHEN B enters `llm_trigger` state THEN the prompt includes the message and instructs B to respond
- GIVEN B's LLM response includes `say_to` to Alice WHEN the response is processed THEN the consumed dialogue message is removed from B's queue
- GIVEN Agent A has 2 `dialogue` messages and 1 `greeting` in its queue WHEN A's LLM response is processed containing a `say_to` THEN the 2 dialogue and 1 greeting messages are removed from A's queue
- GIVEN an agent has a `trade_proposal` and a `dialogue` message WHEN LLM response is processed THEN only the `dialogue` is consumed; `trade_proposal` remains
- GIVEN an agent with messages in `conversation_queue` WHEN the prompt is built THEN `JSON_FORMAT_INSTRUCTION` includes text instructing the LLM to respond to received messages
- GIVEN an agent with no messages WHEN the prompt is built THEN the response guidance is still present but the LLM may choose not to use `say_to`
- GIVEN Agent B has a `dialogue` message from Alice with text "Hello!" WHEN B's prompt is built THEN SOCIAL CONTEXT includes `- From Alice: dialogue: Hello!`
- GIVEN Agent B has a `greeting` message from Bob WHEN B's prompt is built THEN SOCIAL CONTEXT includes `- From Bob: greeting: greeted you`
- GIVEN Alice (gatherer) at (5,5) and Bob (builder) at (7,5) WHEN RealLLMOrchestrator builds Alice's prompt THEN NEARBY AGENTS includes "Bob (builder) at distance 2"
- GIVEN Alice is alone (no agents within 5 tiles) WHEN her prompt is built THEN NEARBY AGENTS shows "(none)"
- GIVEN Agent A has relationship score 0.8 with Agent B WHEN A's prompt shows B's message THEN `(relationship: 0.8)` appears in the social context line
- GIVEN Agent A has no relationship with Agent C WHEN A's prompt shows C's message THEN `(relationship: neutral)` appears
- GIVEN Agent B has a `share_knowledge` message for POISONOUS_BERRY with `{"is_poisonous": true}` WHEN the engine processes the queue THEN B's `knowledge["POISONOUS_BERRY"]["is_poisonous"]` is True AND the message is removed from B's queue
- GIVEN a `share_knowledge` message is processed WHEN the event queue is drained THEN a SimEvent with type `knowledge_shared` is present

**F7 — Colony Information Panel**

- GIVEN a running simulation with 10 agents (3 births, 1 death) WHEN `GET /api/colony` is called THEN the response includes `population=9`, `births=3`, `deaths=1`, `alive=9`, `dead=1`, plus resource totals and faction list
- GIVEN a WebSocket snapshot is broadcast WHEN the `colony_stats` field is present THEN the frontend ColonyInfo panel updates without additional API calls
- GIVEN ColonyInfo.svelte is mounted and receives colony stats via the store WHEN stats change THEN the display auto-updates via Svelte 5 reactivity

**F8 — Relationship-Based Reproduction**

- GIVEN Agent A and Agent B have `interaction_count=0` WHEN Agent A's FSM evaluates reproduction partners THEN `_find_reproduction_partner()` returns `None`
- GIVEN Agent A and Agent B have `interaction_count=7` (≥ threshold=5) WHEN Agent A's FSM evaluates reproduction partners THEN `_find_reproduction_partner()` returns Agent B's ID as a candidate
- GIVEN two agents with `last_interaction_tick=100` at tick 300 WHEN the decay check runs THEN `interaction_count` has decremented by `floor((300-100)/DECAY_INTERVAL)` (minimum 0)
- GIVEN the AgentInspector panel WHEN an agent has 2 relationships THEN the panel shows a "Relationships" section listing both agents with their interaction count and score
- GIVEN an agent's relationships include Agent B with `score=0.8` WHEN Agent A evaluates trade with Agent B THEN the LLM receives the positive relationship score as favorable context

**F7 — Colony Information Panel (Extended Metrics)**

- GIVEN a simulation with 5 structures (2 houses, 1 forge, 1 farm, 1 wall) WHEN `GET /api/colony` is called THEN the response includes `total_structures=5` and `structures_by_type={"house": 2, "forge": 1, "farm": 1, "wall": 1}`

**F9 — New ActionTypes**

- GIVEN the ActionType enum WHEN checking for MINE, HUNT, FISH, FARM, CRAFT, BUILD, ATTACK, GUARD, EXPLORE, HEAL THEN each exists as a valid member
- GIVEN the REGISTRY dict WHEN all 10 new ActionTypes are checked THEN each has a corresponding handler function registered

**F10 — Agent Equipment Fields**

- GIVEN a newly created Agent WHEN the agent is initialized THEN `agent.equipment` is `{"weapon": "fist", "armor": "none", "tool": "none"}`
- GIVEN an agent with `equipment={"weapon": "spear", "armor": "hide_vest", "tool": "stone_axe"}` WHEN a WorldSnapshot is built THEN the agent's AgentState includes the `equipment` field with the same values

**F11 — Role-Specific Behavioral Context in LLM Prompts**

- GIVEN an agent with role `hunter` WHEN `build_agent_prompt()` is called THEN the system prompt includes role-specific guidance (e.g., "As a hunter, you track and hunt animals for food and hide.")
- GIVEN the `JSON_FORMAT_INSTRUCTION` WHEN inspected THEN the steps action enum includes "mine", "hunt", "fish", "farm", "craft", "build", "attack", "guard", "explore", "heal"

**F12 — Structure Awareness in LLM Prompts**

- GIVEN an agent near a forge structure at position (12,12) and a farm at (15,15) WHEN the LLM prompt is built THEN the prompt includes a `NEARBY STRUCTURES:` section listing the forge and farm with their positions

**F13 — Equipment in AgentState Schema**

- GIVEN an AgentState created from an agent with equipment WHEN the AgentState is serialized to JSON THEN the JSON includes `"equipment": {"weapon": "...", "armor": "...", "tool": "..."}`

**F14 — Structures in WorldSnapshot Schema**

- GIVEN a WorldSnapshot built with 2 active structures WHEN the snapshot is serialized THEN the `structures` list contains both structure dicts with all specified fields (id, type, position, owner_id, health, max_health, properties)

#### Acceptance Criteria

- [x] **F1**: An action's result (success/failure, stat changes, inventory changes) appears in the next LLM prompt as `last_action_result`. First-tick agents gracefully pass `null`. LLM timeouts fall back to instincts and do NOT accumulate stale context.
- [x] **F2**: Resource subtypes have hidden properties not visible in the world snapshot. Agents learn properties by consuming the resource. Knowledge is per-agent (not shared globally). Knowledge is shareable via conversation. The LLM prompt includes known knowledge about resources.
- [x] **F3**: Newborn agents are born adjacent to parent with `is_child=True`. Children cannot EAT/DRINK independently — the caregiver's FSM triggers FEED_CHILD. Stats are inherited with random offset. Children mature at `maturity_age` ticks. Orphaned children are adopted by nearest adult or die if none exists.
- [x] **F4**: Faction CRUD works. Agents show faction color in the canvas. Agent death transfers inventory to faction shared pool. Same-faction members get trade preference via LLM context.
- [x] **F5**: TRADE action works between nearby agents. Proposer specifies offer/request. Target LLM evaluates and accepts/rejects. Accepted trades execute atomically. Rejected trades log without inventory changes. Successful trades increment interaction counts.
- [x] **F6**: Proximity-based conversations trigger automatically. Messages are enqueued FIFO (max 50) with `sender_name` populated. LLM processes messages during the next planning cycle with readable social context (sender name, role, text, relationship score) and response guidance. Consumed dialogue/greeting messages are removed from the queue after LLM processing; trade_proposal messages preserved. `RealLLMOrchestrator` computes actual nearby friendly agents by position and faction. `share_knowledge` messages are processed in the tick loop, updating the recipient's knowledge store and emitting `knowledge_shared` events. Knowledge is shared via conversation messages. Interaction counts increment. Events are logged. Cap of 5 conversation pairs per tick enforced.
- [x] **F7**: `GET /api/colony` returns demographics, resource totals, structure counts, and equipment stats. WebSocket snapshot includes `colony_stats` with structure/equipment metrics. ColonyInfo.svelte renders population, births, deaths, resource totals, structures, and factions. Frontend HUD shows key metric widgets.
- [x] **F8**: `relationships` dict tracks interactions per agent pair. REPRODUCE is gated by `interaction_count >= INTERACTION_THRESHOLD`. Relationships decay over time without interaction. AgentInspector shows relationships. Unconditional reproduction is replaced.
- [x] **F9**: ActionType enum includes all 20 types. All new action types (MINE, HUNT, FISH, FARM, CRAFT, BUILD, ATTACK, GUARD, EXPLORE, HEAL) registered in REGISTRY with handler functions.
- [x] **F10**: Agent dataclass has equipment field with defaults. Serialized in AgentState and WebSocket snapshots.
- [x] **F11**: LLM prompts include role-specific behavioral guidance. JSON_FORMAT_INSTRUCTION includes all new actions.
- [x] **F12**: LLM prompts include NEARBY STRUCTURES section with type, position, owner, health.
- [x] **F13**: AgentState Pydantic model includes equipment field.
- [x] **F14**: WorldSnapshot includes optional structures list with all required fields.
- [x] **Backward compatibility**: All existing simulation-engine tests pass without modification. Existing agents without `faction_id`, `is_child`, `knowledge`, `relationships`, or `equipment` continue to function with default values.
- [ ] **Performance**: Tick loop with all social features active (20 agents, 3 factions, conversations, trades) completes within 150ms per tick on reference hardware.
