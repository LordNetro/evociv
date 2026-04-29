# Design: Agent Society

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SimulationEngine                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Needs    │  │ FSM      │  │ LLM      │  │ SocialSubsystems  │  │
│  │ Decay    │→ │ Runner   │→ │ Polling  │  │                   │  │
│  └──────────┘  └──────────┘  └──────────┘  │ ┌───────────────┐ │  │
│                                              │ │ Conversation  │ │  │
│  ┌──────────────────────────────────────┐   │ │ Manager       │ │  │
│  │          Tick Phases                 │   │ └───────────────┘ │  │
│  │ 1. needs 2. fsm 3. events 4. llm    │   │ ┌───────────────┐ │  │
│  │ 5. regen 6. proximity 7. social     │   │ │ Trade Handler │ │  │
│  │ 8. faction 9. snapshot 10. db       │   │ └───────────────┘ │  │
│  └──────────────────────────────────────┘   │ ┌───────────────┐ │  │
│                                              │ │ Faction Mgmt  │ │  │
│  ┌──────────┐  ┌──────────┐                 │ └───────────────┘ │  │
│  │ World    │  │ Agent    │                 │ ┌───────────────┐ │  │
│  │ (subtypes)│  │ (social) │                 │ │ Knowledge     │ │  │
│  └──────────┘  └──────────┘                 │ │ Store        │ │  │
│                                              │ └───────────────┘ │  │
│  ┌──────────────────┐  ┌─────────────────┐  └───────────────────┘  │
│  │ EventQueue       │  │ SnapshotBuilder │                        │
│  │ (new types added)│  │ (colony_stats)  │                        │
│  └──────────────────┘  └─────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
                            │ WebSocket
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Frontend (Svelte 5)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │ Canvas       │  │ Agent        │  │ ColonyInfo Panel          │  │
│  │ (faction     │  │ Inspector    │  │ (demographics, resources, │  │
│  │  borders)    │  │ (relationships)│  │ factions, HUD widgets)   │  │
│  └──────────────┘  └──────────────┘  └───────────────────────────┘  │
│                      ▲ store.subscribe                               │
│              ┌───────┴────────┐                                      │
│              │ simulationStore │                                      │
│              │ (social data)   │                                      │
│              └────────────────┘                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Architecture Decisions

| Decision | Options | Choice | Rationale |
|----------|---------|--------|-----------|
| Social subsystems as engine-owned managers vs standalone service | Standalone service vs Engine-owned managers | Engine-owned manager objects | Simpler lifecycle — no extra async service; shares the same event queue and snapshot cycle; minimal coupling |
| Knowledge store in Agent dataclass vs separate service | Dict on Agent vs external db | Dict on Agent (`knowledge: dict[str, dict]`) | Per-agent, in-memory, no persistence needed across runs; matches existing `inventory` pattern |
| Conversation message format | NL vs structured dict | Structured dict (`{"type": "...", ...}`) | Per spec — NL generation deferred; structured is parseable by LLM without hallucination risk |
| Faction persistence | File vs DB vs in-memory | In-memory dict on engine (`dict[str, Faction]`) | Matches existing in-memory pattern of engine; no DB migrations needed |
| Colony stats — REST vs WS-only | Both vs WS-only | Both (REST for initial load, WS for live updates) | REST gives full data on page load; WS delta for live updates without polling |
| Action feedback mechanism | `ActionResult` stored on Agent vs passed in prompt | `ActionResult` stored in `Agent.last_action_result: Optional[ActionResult]` | LLM prompt builder reads it from agent; reset after read to avoid stale context |

## Module-by-Module Design

### 1. Data Layer

#### New entities

```
backend/app/simulation/
├── faction.py          # NEW — Faction dataclass + CRUD
├── conversation.py     # NEW — Message dataclass + ConversationManager
├── knowledge.py        # NEW — KnowledgeStore dataclass (per-agent)
└── colony.py           # NEW — ColonyStats collector
```

**Faction** (`faction.py`):
```python
@dataclass
class Faction:
    id: str
    name: str
    color: str           # hex, e.g. "#FF0000"
    member_ids: list[str]
    shared_resources: dict[str, int]  # resource_name → count
```

**Message** (`conversation.py`):
```python
@dataclass
class Message:
    sender_id: str
    content: dict        # structured: {"type": "greeting"|"share_knowledge"|"trade_proposal"|...}
    tick: int

class ConversationManager:
    max_pairs_per_tick: int = 5
    max_queue_size: int = 50
    _pending_pairs: list[tuple[str, str]]  # deferred pairs
    def detect_encounters(agents, radius, tick) -> None
    def process_next_pair(agent_a, agent_b, world) -> tuple[Message, Message] | None
```

**Knowledge** (`knowledge.py`):
```python
# Each agent gets: agent.knowledge: dict[str, dict[str, Any]]
# Key: subtype name (e.g. "POISONOUS_BERRY")
# Value: {property: value} (e.g. {"is_poisonous": True})
```

**ColonyStats** (`colony.py`):
```python
@dataclass
class ColonyStats:
    population: int
    births: int           # session total
    deaths: int           # session total
    role_distribution: dict[str, int]
    sex_distribution: dict[str, int]
    age_groups: dict[str, int]  # "child": N, "adult": N, "elder": N
    total_resources: dict[str, int]
    factions: list[FactionSummary]
```

#### Changes to existing models

**Agent** — new fields:
- `relationships: dict[str, RelationshipData]` — F8
- `faction_id: str | None = None` — F4
- `is_child: bool = False` / `parent_id: str | None = None` / `maturity_age: int = 500` — F3
- `knowledge: dict[str, dict[str, Any]] = field(default_factory=dict)` — F2
- `conversation_queue: list[Message] = field(default_factory=list)` — F6
- `last_action_result: Optional[ActionResult] = None` — F1
- `interaction_count: int = 0` (legacy counter), replaced by `relationships` dict lookup

```python
@dataclass
class RelationshipData:
    interaction_count: int
    last_interaction_tick: int
    score: float  # -1.0 to 1.0
```

**Tile** (`world.py`) — new field:
- `subtype: str | None = None` — e.g. "POISONOUS_BERRY", "SAFE_BERRY", "OAK_TREE"
- `hidden_properties: dict[str, Any] = field(default_factory=dict)` — e.g. `{"is_poisonous": True}`

**ActionResult** (`actions.py`) — add `action_type: ActionType` and `action_summary: str`:
```python
@dataclass
class ActionResult:
    success: bool = True
    events: list[dict] = field(default_factory=list)
    interrupted: bool = False
    state_changes: dict[str, Any] = field(default_factory=dict)
    action_type: ActionType | None = None     # NEW
    action_summary: str = ""                  # NEW — e.g. "hunger:-30, wood:+5"
```

**AgentState** (Pydantic schema, `schemas.py`) — new fields:
- `relationships: dict[str, dict] = {}` — F8
- `faction_id: str | None = None` — F4
- `is_child: bool = False` — F3
- `knowledge: list[str] = []` — F2 (subset: list of known subtype names)
- `interaction_count: int = 0` (aggregate for quick display)

**WorldSnapshot** (Pydantic) — new field:
- `colony_stats: dict | None = None` — F7 (subset: population, births, deaths, total_resources)

**SimEvent** (`event_queue.py`) — new event types:
- `"trade"`, `"socialize"`, `"faction_join"`, `"faction_leave"`, `"knowledge_shared"`, `"adoption"`

#### ORM changes (`db/models.py`)

- `TickMetrics`: add `total_factions`, `total_children` columns (non-breaking, nullable default 0).
- No new tables needed — faction data is transient (in-memory).

### 2. Simulation Engine Changes

#### FSM state changes

| Current State | New Transitions | Feature |
|--------------|-----------------|---------|
| `"idle"` | → `"evaluate"` (unchanged) | — |
| `"evaluate"` | **NEW**: check conversation_queue → process social message / trade proposal | F5, F6 |
| `"evaluate"` | **NEW**: if `is_child`, skip EAT/DRINK actions | F3 |
| `"evaluate"` | **MODIFIED**: REPRODUCE gated by `interaction_count >= threshold` | F8 |
| `"evaluate"` | **MODIFIED**: LLM prompt includes `last_action_result` context | F1 |
| `"llm_trigger"` | **MODIFIED**: `build_prompt()` includes knowledge + relationships + action result | F1, F2, F8 |
| New: `"social_interaction"` | Agent processes conversation queue during this dedicated state | F6 |

#### New method: `_process_social_interactions(tick)`

Called in a new tick phase between proximity checks and snapshot:

```python
async def _process_social_interactions(self, tick: int) -> None:
    # 1. Detect encounters via proximity (reuse existing check_proximity_encounters)
    # 2. For each pair within radius, enqueue Messages in both agents' queues
    # 3. Enforce max 5 pairs/tick; defer remainder
    # 4. For agents in IDLE with non-empty queue, transition to llm_trigger
    #    with the queue content as trigger context
    # 5. Process trade proposals (evaluate target agent's response)
```

#### New tick phases in `_tick()`:

```
1. _process_needs(tick)
2. For each agent: _run_agent_fsm(agent, tick)
3. _process_social_interactions(tick)       # NEW — conversations & trade
4. _process_faction_agent_death(tick)        # NEW — transfer inventory on death
5. self.event_queue.drain()
6. _poll_llm_responses(tick)
7. self.world.regenerate_resources()
8. check_proximity_encounters()             # Existing (encounter events)
9. check_resource_discoveries()             # Existing (now includes subtype detection)
10. Build + broadcast snapshot (with colony_stats)
```

#### Action changes

**New ActionType values:**
- `TRADE = "trade"` — with handler `handle_trade()` in `actions.py`
- `SOCIALIZE = "socialize"` — trigger for conversation processing
- `FEED_CHILD = "feed_child"` — caregiver feeds child agent

**Modified handlers:**

| Handler | Change | Feature |
|---------|--------|---------|
| `handle_eat()` | Reveal hidden properties of consumed resource subtype → update agent.knowledge | F2 |
| `handle_eat()` | If agent is_child → block action | F3 |
| `handle_reproduce()` | Check `interaction_count >= INTERACTION_THRESHOLD` → else fail | F8 |
| All handlers | Populate `ActionResult.action_type` and `action_summary` | F1 |

**New handlers:**

```
handle_trade(agent, world, target, step) -> ActionResult
  - Validate proposer has offer resources
  - Enqueue trade proposal in target's conversation_queue
  - Target LLM evaluates in next tick
  - On accept: atomic swap; on reject: no-op
  - Increment interaction_count for both

handle_feed_child(agent, world, target, step) -> ActionResult
  - target = child_id
  - Transfer 1 berry from caregiver to satisfy child hunger -30
  - Child must be within interaction radius
```

#### Faction management (new `faction.py`):

```python
class FactionManager:
    def __init__(self): self.factions: dict[str, Faction] = {}
    def create(name, color) -> Faction
    def delete(faction_id) -> bool
    def join(agent_id, faction_id) -> bool
    def leave(agent_id, faction_id) -> bool
    def list_all() -> list[FactionSummary]
    def transfer_inventory_on_death(agent) -> None
    def get_faction(faction_id) -> Faction | None
    def get_all() -> dict[str, Faction]
```

### 3. AI / LLM Integration

#### Prompt changes (`prompts.py`)

**`build_agent_prompt()`** gets new parameters and sections:

```
LAST ACTION RESULT:
- Action: {action_type}
- Success: {true/false}
- Effects: {action_summary}   # e.g. "hunger:-30, wood:+3, food:-1"

KNOWLEDGE:
- You know: POISONOUS_BERRY is poisonous
- You know: OAK_TREE provides strong wood

RELATIONSHIPS:
- Mila: interaction_count=7, score=0.8 (faction ally)
- Kael: interaction_count=2, score=0.3

FACTION:
- You are a member of the "River Clan" (color: #00FF00)

CHILD STATUS:
- You are caring for child {name} (hunger={h}, thirst={t})
```

New constants:
```python
INTERACTION_THRESHOLD = 5   # for F8
DECAY_INTERVAL = 100        # ticks before relationship decays
```

**JSON format instruction** updated to include new action types:
```json
{
  "steps": [{
    "action": "move" | "chop" | "drink" | "eat" | "gather" | "rest" | "reproduce" | "trade" | "socialize" | "feed_child",
    "target": [x, y] or null or agent_id,
    ...
  }]
}
```

For `TRADE`:
```json
{
  "action": "trade",
  "target": "agent_002",
  "offer": {"wood": 3},
  "request": {"berry": 5},
  "duration_secs": 5,
  "reason": "Need food, have spare wood"
}
```

#### Orchestrator changes (`orchestrator.py`)

`build_prompt()` in `RealLLMOrchestrator` — enhanced:
- Read `agent.last_action_result` → include in prompt
- Read `agent.knowledge` → include as formatted string
- Read `agent.relationships` → include key relationships
- Read `agent.faction_id` → include faction context
- Read `agent.is_child` / `agent.parent_id` → skip LLM for infants (instinct-only)

After prompt consumed, reset `agent.last_action_result = None` (prevent stale context accumulation).

**Concurrency management:**
- Existing `_llm_semaphore = Semaphore(1)` already serializes Ollama calls — no change needed.
- Social interactions (trade decisions) share the same semaphore — OK since they're per-agent.
- Timeout fallback: trade rejection is default on timeout (safe default).

### 4. Frontend

#### New components

| Component | File | Purpose |
|-----------|------|---------|
| `ColonyInfo.svelte` | `frontend/src/lib/components/ColonyInfo.svelte` | Demographics panel: pop, births, deaths, role/age distribution, resources, factions |
| `HudWidgets.svelte` | `frontend/src/lib/components/HudWidgets.svelte` | Minimal HUD: population, births, deaths counters |

#### Modified components

**`AgentInspector.svelte`** — add sections:
- "Relationships" — list of known agents with interaction_count, score, last_interaction_tick
- "Faction" — faction name + color swatch if member
- "Knowledge" — known resource subtypes
- "Child Status" — if `is_child`, show parent_id and maturity progress

#### Canvas changes (`entities.ts`)

- **AgentRenderData** — add `factionColor: string | null` field
- **draw()** — if `a.factionColor` set, render colored border/ring around agent circle:
  ```typescript
  if (a.factionColor) {
    ctx.beginPath();
    ctx.arc(px, py, RADIUS + 3, 0, Math.PI * 2);
    ctx.strokeStyle = a.factionColor;
    ctx.lineWidth = 3;
    ctx.stroke();
  }
  ```
- **updateFromSnapshot()** — read `faction_id` from state, resolve color via lookup

#### Store changes (`simulationStore.svelte.js`)

- Add new fields to `SimulationState` type:
  - `colony_stats: object`
  - `factions: Record<string, {id, name, color, member_count, shared_resources}>`
- `updateFromSnapshot()` — consume `colony_stats` and `factions` from snapshot payload

## Integration Points

```
Feature         Produces                    Consumes                    Via
──────          ────────                    ────────                    ───
F1 (feedback)   ActionResult on Agent        LLM prompt builder         Agent.last_action_result
F2 (knowledge)  agent.knowledge dict         LLM prompt builder         build_prompt() reads knowledge
                hidden properties on Tile    Agent consume action       handle_eat() reveals
                knowledge shared via Msg     ConversationManager        Message.content
F3 (childhood)  agent.is_child field         FSM evaluate() blocks      agent.current_action check
                parent_id                    FEED_CHILD action          handle_feed_child()
F4 (factions)   Faction dataclass            Snapshot builder           engine.faction_manager
                agent.faction_id             Canvas renderer            agent.faction_id → color
                shared_resources             Death handler               faction_manager.transfer()
F5 (trade)      Trade proposal Message       Target LLM eval            conversation_queue
                action result                Tick phase 3               _process_social_interactions()
F6 (social)     Message enqueue              Agent conversation_queue   conversation_manager
                knowledge share              Target knowledge store     Message.content["share_knowledge"]
F7 (colony UI)  ColonyStats                  Snapshot.colony_stats       colony.py collector
                GET /api/colony               ColonyInfo.svelte          REST endpoint
F8 (relations)  relationships dict           REPRODUCE gating            _find_reproduction_partner()
                interaction_count inc       Relationship decay           _process_needs() each tick
```

## Data Flow Diagrams

### F1 — LLM Action Feedback (per tick per agent)

```
handle_action() → ActionResult(action_type, success, action_summary)
       │
       ▼
agent.last_action_result = result
       │
       ▼  (next FSM cycle triggered)
build_prompt() reads agent.last_action_result
       │
       ▼  (included in prompt)
LLM receives: "LAST ACTION RESULT: CHOP success, effects: wood:+3, energy:-10"
       │
       ▼
agent.last_action_result = None  (consumed)
```

### F2 — Knowledge Discovery & Sharing

```
Agent steps on/consumes resource
       │
       ▼
handle_eat() checks tile.subtype → tile.hidden_properties
       │
       ▼
agent.knowledge["POISONOUS_BERRY"] = {"is_poisonous": True}
       │
       ▼
build_prompt(): "You know POISONOUS_BERRY is poisonous"
       │
       ▼
[Optional] Agent shares via SOCIALIZE → Message.content = {"type": "share_knowledge", "subtype": "POISONOUS_BERRY", "properties": {"is_poisonous": True}}
       │
       ▼
Receiver agent.knowledge updated
```

### F5 — Trade Flow

```
Agent A (proposer) LLM decides to trade → sets action=TRADE, target=agent_002, offer={wood:3}, request={berry:5}
       │
       ▼
FSM executing: handle_trade() called
       │
       ▼
Validates A has 3 wood → enqueues Message in B's conversation_queue: {"type": "trade_proposal", "from": "A", "offer": {...}, "request": {...}}
       │
       ▼
Next tick: B's FSM processes queue → LLM prompt includes trade proposal context
       │
       ├── Accept → action=TRADE executed → atomic swap → interaction_count++
       │
       └── Reject/timeout → no-op → log SimEvent(type="trade", success=false)
```

### F8 — Relationship-based Reproduction

```
Trade/Conversation/Any interaction between A and B
       │
       ▼
A.relationships[B.id].interaction_count++
A.relationships[B.id].score += delta  (trade=+0.2, socialize=+0.1)
B.relationships[A.id].interaction_count++
B.relationships[A.id].score += delta
       │
       ▼
Each tick in _process_needs():
  - Check decay: if tick - last_interaction_tick > DECAY_INTERVAL → decrement count
       │
       ▼
_find_reproduction_partner(agent):
  - Only considers agents with relationships[other].interaction_count >= INTERACTION_THRESHOLD (5)
  - Also checks compatibility: opposite sex, energy > 20, within radius
       │
       ▼
If no partner found → skip reproduction → LLM for higher-level planning
```

## Testing Strategy

| Layer | Feature | Tests | Approach |
|-------|---------|-------|----------|
| **Unit** | F1 | `test_action_result_captured` | Create ActionResult, assign to agent, verify `build_prompt()` includes it |
| **Unit** | F1 | `test_action_result_null_on_first_tick` | New agent → `last_action_result` is None |
| **Unit** | F1 | `test_action_result_cleared_after_read` | After prompt built, verify field is None |
| **Unit** | F2 | `test_tile_with_subtype` | Create Tile with subtype+hidden, verify world snapshot does NOT expose hidden |
| **Unit** | F2 | `test_eat_reveals_hidden_properties` | Agent eats POISONOUS_BERRY → `knowledge["POISONOUS_BERRY"]` populated |
| **Unit** | F2 | `test_knowledge_is_per_agent` | Two agents, one eats → knowledge differs |
| **Unit** | F2 | `test_knowledge_in_prompt` | Agent with knowledge → string appears in built prompt |
| **Unit** | F2 | `test_knowledge_share_via_message` | Direct update of other agent's knowledge via Message |
| **Unit** | F3 | `test_child_blocks_eat` | Agent with is_child=True → handle_eat() returns failure |
| **Unit** | F3 | `test_feed_child_action` | Caregiver has berries, child nearby → hunger decreases, inventory decreases |
| **Unit** | F3 | `test_child_stat_inheritance` | Parent stats ± random(0,15), children within expected range |
| **Unit** | F3 | `test_child_maturity` | Tick reaches maturity_age → is_child=False |
| **Unit** | F3 | `test_orphan_adoption` | Caregiver dies, closest adult within radius adopts |
| **Unit** | F4 | `test_faction_crud` | Create, delete, join, leave, list |
| **Unit** | F4 | `test_faction_death_transfer` | Agent dies → inventory moves to faction.shared_resources |
| **Unit** | F5 | `test_trade_atomic_swap` | Both have sufficient → both inventories update correctly |
| **Unit** | F5 | `test_trade_insufficient_funds` | Proposer lacks resources → fail, no change |
| **Unit** | F5 | `test_trade_interaction_count` | Successful trade increments both agents' count |
| **Unit** | F6 | `test_conversation_enqueue` | Two agents within radius → messages in both queues |
| **Unit** | F6 | `test_max_queue_size` | 60 messages pushed → only last 50 kept |
| **Unit** | F6 | `test_max_pairs_per_tick` | 10 pairs pending → only 5 processed, 5 deferred |
| **Unit** | F8 | `test_relationship_data` | Interaction between agents → relationship entry created with correct fields |
| **Unit** | F8 | `test_reproduce_gated_by_interactions` | interaction_count < threshold → no partner found |
| **Unit** | F8 | `test_relationship_decay` | After decay interval, interaction_count decrements |
| **Integration** | F3+F8 | `test_child_spawn_adjacent_to_parent` | After F8 reproduction, child adjacent to parent tile |
| **Integration** | F5+F6+F8 | `test_trade_increments_interaction_count` | Full trade flow → interaction_count updated for both |
| **Integration** | F6+F2 | `test_knowledge_shared_via_conversation` | Full conversation flow → knowledge propagates |
| **Integration** | F7 | `test_colony_endpoint` | HTTP GET /api/colony → correct JSON structure |
| **Integration** | F7 | `test_colony_stats_in_snapshot` | WebSocket snapshot includes colony_stats |
| **Integration** | Engine | `test_social_tick_performance` | 20 agents, 3 factions, conversations, trades → <150ms/tick |
| **Regression** | All | `test_existing_engine_tests_pass` | All current tests run without modification |

**Mock strategy:**
- `MockLLMOrchestrator`: update `build_prompt()` to verify new context sections are present. Use `success_rate=1.0` for deterministic tests.
- Trade decisions: mock LLM to return accept or reject plan deterministically.
- Conversation: mock LLM response to include reply/share_knowledge actions.
- Faction: use standalone `FactionManager` tests without engine.

## Performance & Limits

| Limit | Value | Location | Rationale |
|-------|-------|----------|-----------|
| Conversation queue size | 50 messages/agent | `conversation.py` | Prevents memory bloat; 50 is enough for recent context |
| Conversation pairs/tick | 5 | `ConversationManager` | Prevents tick loop slowdown; deferred to next tick |
| LLM concurrency | Semaphore(1) | `orchestrator.py` (existing) | Avoids overloading Ollama; trade decisions share this |
| LLM timeout | 30s (configurable) | `settings.llm_timeout` | Existing; trade rejection on timeout is safe default |
| Action feedback stale guard | 1 tick lifespan | `agent.last_action_result` | Reset to None after prompt build; never accumulates |
| Relationship decay interval | 100 ticks | `engine.py` constant | Agents need ongoing interaction to maintain bonds |
| Reproduction interaction threshold | 5 | `engine.py` constant | Minimum meaningful interactions before reproduction |
| Faction soft cap | None (emergent) | `faction_manager` | Let dynamics emerge naturally; no hard cap |
| Population cap | 20 (existing) | `engine.py` MAX_POPULATION | No change; existing limit still applies |
| Max events in snapshot | 100 (existing) | `simulationStore.svelte.js` | No change; frontend limit |
| Colony stats snapshot size | ~1KB | `WorldSnapshot.colony_stats` | Small subset of full snapshot; negligible overhead |

**Performance budget for tick loop with full social features (20 agents, 3 factions):**

| Phase | Est. time | Notes |
|-------|-----------|-------|
| Needs decay | <1ms | O(n) linear |
| FSM run (20 agents) | ~5ms | Includes instinct checks |
| Social interactions | ~3ms | Max 5 pairs; message enqueue is O(k) |
| Faction processing | <1ms | Death transfer check |
| LLM poll | <1ms | Completed future check |
| World regen | ~2ms | O(width*height) |
| Proximity | ~1ms | O(n²/2) for 20 = 190 pairs |
| Snapshot build | ~5ms | All agents + dirty tiles |
| **Total** | **<20ms** | Well under 150ms budget |

## Open Questions

- [ ] **F3 adoption**: Should adoption be automatic (nearest adult) or require LLM evaluation on the adopter? The spec permits either. Design defaults to automatic for reliability, but LLM opt-in could add emergent storytelling. Decision: automatic + SimEvent log ("X adopted Y").
- [ ] **F5 trade rejection reason**: Should the LLM provide a rejection reason (for UX) or just silent reject? Tradeoff: more data vs slower ticks. Decision: include rejection reason in the SimEvent log (mutable in implementation).
- [ ] **F6 conversation depth**: Should conversations be multi-turn within a single tick? Spec implies single message per encounter per tick. Decision: 1 message per agent per encounter per tick (matches spec).
- [ ] **F7 colony endpoint frequency**: Should there be a rate limit on GET /api/colony? Decision: not needed — lightweight read from engine state, no DB query.

## Migration / Rollout

- **No data migration required.** All new fields have safe defaults (`None`, `{}`, `False`) — existing agents are backward compatible.
- **Phased rollout per proposal**: Phase 1 (F1+F8) → Phase 2 (F6) → Phase 3 (F2+F5) → Phase 4 (F3+F4) → Phase 5 (F7). Each phase independently merges to main.
- **Rollback plan per proposal**: revert `agent.py`, `actions.py`, `engine.py`, `world.py`, `simulationStore.svelte.js`, delete new modules (`knowledge.py`, `faction.py`, `conversation.py`, `colony.py`, `ColonyInfo.svelte`, `HudWidgets.svelte`).
