# Spec: agent-society

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
| F4-R7 | When a faction member dies, their personal inventory MUST be transferred to the faction's `shared_resources`. | MUST |

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

| # | Requirement | Strength |
|---|-------------|----------|
| F6-R1 | A new `SOCIALIZE` action type MUST be added. The action is triggered automatically when two agents are within interaction radius (≤ 3 tiles). | MUST |
| F6-R2 | Each agent MUST have a `conversation_queue: list[Message]` (FIFO, max 50 messages). Each `Message` contains: `sender_id`, `content` (structured dict), and `tick`. | MUST |
| F6-R3 | When a proximity encounter is detected, a `Message` is enqueued in both agents' queues. The message content describes the encounter (e.g., `{"type": "greeting", "agent_name": "Alice"}`). | MUST |
| F6-R4 | On each tick, an agent in IDLE state with non-empty `conversation_queue` MUST process the next message in its LLM prompt. The LLM decides how to respond (reply, share knowledge, ignore, propose trade, etc.). | MUST |
| F6-R5 | Agents MAY share knowledge from their `knowledge` store (F2) through conversation. When an agent shares a known property, the receiving agent's `knowledge` store MUST be updated. | MUST |
| F6-R6 | Each successful conversation interaction MUST increment the `interaction_count` for both participants, feeding into F8's relationship system. | MUST |
| F6-R7 | All conversation events (initiation, messages, knowledge shared) MUST be recorded as SimEvents in the event log with type `"socialize"`. | MUST |
| F6-R8 | To prevent tick-loop spam, a maximum of 5 conversation pairs per tick MUST be processed. Additional pending pairs are deferred to the next tick. | MUST |

**F7 — Colony Information Panel**

| # | Requirement | Strength |
|---|-------------|----------|
| F7-R1 | A new REST endpoint `GET /api/colony` MUST return colony-level statistics: total population, births count (agents spawned this session), deaths count, alive/dead ratio, distribution by role, sex, age groups, total resources across all agents, and active factions list. | MUST |
| F7-R2 | The WebSocket snapshot MUST be extended with a `colony_stats` field containing a subset of frequently-changing metrics: population, births, deaths, and total resources. | MUST |
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
- GIVEN two agents in the same faction WHEN one proposes a trade THEN the LLM prompt includes context that they are faction allies, increasing acceptance likelihood
- GIVEN a faction with 3 members WHEN queried via GET /api/factions THEN the response includes id, name, color, member_count=3, and shared_resources

**F5 — Trading**

- GIVEN Agent A at (10,10) and Agent B at (11,10) within interaction radius WHEN Agent A initiates TRADE with offer={"wood": 3} and request={"berry": 5} THEN the trade proposal is added to Agent B's conversation queue
- GIVEN Agent B receives a trade proposal and its LLM accepts WHEN the trade is processed THEN Agent A loses 3 wood, Agent B loses 5 berry, Agent A gains 5 berry, Agent B gains 3 wood (atomic swap)
- GIVEN Agent A has offer={"wood": 10} but only has 3 wood in inventory WHEN the trade is evaluated THEN the action fails with `success=False` and neither inventory is modified
- GIVEN a successful trade between Agent A and Agent B WHEN the trade completes THEN both agents' `interaction_count` increments by 1

**F6 — Socialization and Conversations**

- GIVEN two agents within distance ≤ 3 tiles WHEN the proximity check runs THEN a `Message` is enqueued in both agents' `conversation_queue`
- GIVEN an agent in IDLE state with `conversation_queue` containing 3 messages WHEN the FSM ticks THEN the agent processes the oldest message, the LLM receives the message context and produces a response plan
- GIVEN Agent A shares knowledge about `POISONOUS_BERRY` via a conversation message WHEN Agent B processes the message THEN Agent B's `knowledge` store is updated with the shared information
- GIVEN a conversation event WHEN it occurs THEN a SimEvent with type `"socialize"` is logged containing both agent IDs and message summary
- GIVEN more than 5 conversation pairs are pending in a single tick WHEN the tick processes social interactions THEN only 5 pairs are processed and the remainder are deferred to the next tick

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

#### Acceptance Criteria

- [ ] **F1**: An action's result (success/failure, stat changes, inventory changes) appears in the next LLM prompt as `last_action_result`. First-tick agents gracefully pass `null`. LLM timeouts fall back to instincts and do NOT accumulate stale context.
- [ ] **F2**: Resource subtypes have hidden properties not visible in the world snapshot. Agents learn properties by consuming the resource. Knowledge is per-agent (not shared globally). Knowledge is shareable via conversation. The LLM prompt includes known knowledge about resources.
- [ ] **F3**: Newborn agents are born adjacent to parent with `is_child=True`. Children cannot EAT/DRINK independently — the caregiver's FSM triggers FEED_CHILD. Stats are inherited with random offset. Children mature at `maturity_age` ticks. Orphaned children are adopted by nearest adult or die if none exists.
- [ ] **F4**: Faction CRUD works. Agents show faction color in the canvas. Agent death transfers inventory to faction shared pool. Same-faction members get trade preference via LLM context.
- [ ] **F5**: TRADE action works between nearby agents. Proposer specifies offer/request. Target LLM evaluates and accepts/rejects. Accepted trades execute atomically. Rejected trades log without inventory changes. Successful trades increment interaction counts.
- [ ] **F6**: Proximity-based conversations trigger automatically. Messages are enqueued FIFO (max 50). LLM processes messages during the next planning cycle. Knowledge is shared via conversation messages. Interaction counts increment. Events are logged. Cap of 5 conversation pairs per tick enforced.
- [ ] **F7**: `GET /api/colony` returns demographics and resource totals. WebSocket snapshot includes `colony_stats`. ColonyInfo.svelte renders population, births, deaths, resource totals, and factions. Frontend HUD shows key metric widgets.
- [ ] **F8**: `relationships` dict tracks interactions per agent pair. REPRODUCE is gated by `interaction_count >= INTERACTION_THRESHOLD`. Relationships decay over time without interaction. AgentInspector shows relationships. Unconditional reproduction is replaced.
- [ ] **Backward compatibility**: All existing simulation-engine tests pass without modification. Existing agents without `faction_id`, `is_child`, `knowledge`, or `relationships` continue to function with default values.
- [ ] **Performance**: Tick loop with all social features active (20 agents, 3 factions, conversations, trades) completes within 150ms per tick on reference hardware.
