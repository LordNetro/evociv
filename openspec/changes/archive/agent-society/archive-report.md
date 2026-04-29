# Archive Report: agent-society

## Summary

The "agent-society" change built a complete social simulation layer on top of the existing simulation engine. Agents evolved from isolated, asocial survival to a full society with relationships, conversations, trade, childhood dependency, factions, limited perception (knowledge), LLM action feedback, and colony-level UI. The implementation spanned 8 features across 5 phases, following the SDD workflow through proposal, spec, design, tasks, implementation, and verification phases.

## Features Implemented

- **F1 — LLM-Triggered Action Feedback**: `ActionResult` now carries `action_type` and `action_summary` fields. The result of each action (success/failure, stat deltas, inventory changes) is passed as `last_action_result` to the agent's next LLM prompt. Consumed after prompt build to prevent stale context. LLM timeouts discard the pending result and fall back to instinct behavior.

- **F2 — Limited Knowledge / Perception**: Resource tiles gained `subtype` (e.g., `POISONOUS_BERRY`, `SAFE_BERRY`) and `hidden_properties` (e.g., `{"is_poisonous": True}`) not visible in snapshots. Agents learn hidden properties by consuming resources, stored per-agent in `knowledge` dict. Knowledge appears in LLM prompts and can be shared via conversations. Frontend shows known subtypes in AgentInspector.

- **F3 — Childhood / Parental Care**: Newborn agents spawn with `is_child=True`, `parent_id`, `maturity_age` (300-700 ticks). Children cannot EAT/DRINK independently. The `FEED_CHILD` action lets caregivers reduce child hunger/thirst. Stats are inherited from parent ± random offset. Caregivers prioritize children over own needs. Orphans are adopted by nearest adult or die if none exists.

- **F4 — Factions**: `Faction` dataclass and `FactionManager` with full CRUD. Three default factions (River Clan, Stone Hold, Green Ward). Agents assigned to factions on spawn. Death transfers inventory to faction's `shared_resources`. Same-faction trade preference via LLM context. Canvas renders faction-colored borders. AgentInspector shows faction info.

- **F5 — Trading**: `TRADE` action with offer/request negotiation. Proposer specifies resources to give and request. Target LLM evaluates and accepts/rejects. Accepted trades execute atomically (both inventories updated). Rejected trades log without changes. Successful trades increment `interaction_count` for relationship tracking.

- **F6 — Socialization / Conversations**: `ConversationManager` with proximity-based encounter detection. Messages enqueued FIFO (max 50 per agent). Max 5 conversation pairs per tick. Knowledge sharing happens automatically during encounters via `share_knowledge` messages. Conversation events logged as SimEvents with type `"socialize"`.

- **F7 — Colony Info**: `ColonyStatsCollector` tracks births/deaths/population/resources. REST endpoint `GET /api/colony` returns full demographics. WebSocket snapshot includes `colony_stats` subset. `ColonyInfo.svelte` panel shows population, births, deaths, total resources, and factions. `HudWidgets.svelte` shows key metrics as minimal counters.

- **F8 — Relationship-Based Reproduction**: `RelationshipData` dataclass tracks `interaction_count`, `last_interaction_tick`, and `score` per agent pair. `REPRODUCE` gated by `INTERACTION_THRESHOLD=5`. Relationships decay after 100 ticks without interaction. AgentInspector shows relationships section.

## Files Created (7 new)

- **`backend/app/simulation/faction.py`** — Faction dataclass + FactionManager with full CRUD, default factions, and death inventory transfer
- **`backend/app/simulation/conversation.py`** — Message dataclass + ConversationManager with encounter detection, queue management, and knowledge sharing
- **`backend/app/simulation/colony.py`** — ColonyStats dataclass + ColonyStatsCollector for demographics and resource aggregation
- **`backend/app/api/colony.py`** — FastAPI REST endpoint `GET /api/colony` returning full colony statistics
- **`frontend/src/lib/components/ColonyInfo.svelte`** — Folding panel with population, demographics, resources, and faction cards
- **`frontend/src/lib/components/HudWidgets.svelte`** — Minimal HUD counters for population, births, deaths, and faction count
- **`backend/tests/test_social.py`** — 58 tests covering all social features (F1 through F8)

## Files Modified (14)

- **`backend/app/simulation/agent.py`** — Added `last_action_result`, `relationships`, `knowledge`, `conversation_queue`, `is_child`, `parent_id`, `maturity_age`, `faction_id` fields
- **`backend/app/simulation/actions.py`** — Added `TRADE`, `SOCIALIZE`, `FEED_CHILD` action types and handlers; `action_type`/`action_summary` on `ActionResult`; knowledge reveal in `handle_eat()`
- **`backend/app/simulation/engine.py`** — New tick phases: social interactions, faction processing; `_update_relationship()`, `_find_reproduction_partner()` gated; conversation/faction/colony managers instantiated; colony stats collection; LLM feedback loop
- **`backend/app/simulation/world.py`** — Added `subtype` and `hidden_properties` to Tile
- **`backend/app/ai/prompts.py`** — New prompt sections: `LAST ACTION RESULT`, `KNOWLEDGE`, `SOCIAL CONTEXT`, `FACTION`; expanded JSON format with trade/social/feed_child
- **`backend/app/ai/orchestrator.py`** — Prompt builder enhanced with action feedback, knowledge, faction context, social context
- **`backend/app/models/schemas.py`** — Extended AgentState with relationships, faction_id, is_child, knowledge; WorldSnapshot with colony_stats and factions
- **`backend/app/simulation/snapshot.py`** — Snapshot builder includes relationships, faction_id, is_child, knowledge, colony_stats, factions
- **`backend/app/simulation/event_queue.py`** — Added event types: trade, socialize, faction_join, faction_leave, knowledge_shared, adoption
- **`backend/app/main.py`** — Registered colony router
- **`frontend/src/lib/stores/simulationStore.svelte.js`** — Added `colony_stats` and `factions` fields; updateFromSnapshot consumes social data
- **`frontend/src/lib/components/AgentInspector.svelte`** — Added Relationships, Faction, Knowledge, Child Status sections
- **`frontend/src/lib/canvas/entities.ts`** — Added `factionColor` to AgentRenderData; draws colored border for faction members
- **`frontend/src/lib/canvas/engine.ts`** — Passes faction data to entity updates

## Test Results

- **107 tests passing** (49 existing + 58 new social tests)
  - `test_ai.py`: 10 tests (existing)
  - `test_engine.py`: 36 tests (existing)
  - `test_health.py`: 1 test (existing)
  - `test_websocket.py`: 2 tests (existing)
  - `test_social.py`: 58 tests (new — covers F1 through F8)
- **Frontend**: 0 TypeScript errors (`svelte-check` clean)
- **Backward compatibility**: All existing tests pass without modification

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Social subsystems ownership | Engine-owned manager objects (ConversationManager, FactionManager, ColonyStatsCollector) | Simpler lifecycle — no extra async service; shares the same event queue and snapshot cycle; minimal coupling |
| Knowledge store location | Dict on Agent (`knowledge: dict[str, dict]`) | Per-agent, in-memory, no persistence needed; matches existing inventory pattern |
| Conversation message format | Structured dict (`{"type": "greeting", ...}`) | Parseable by LLM without hallucination risk; NL generation deferred |
| Faction persistence | In-memory dict on engine (`dict[str, Faction]`) | Matches existing in-memory pattern; no DB migrations needed |
| Colony stats delivery | Both REST (initial load) + WebSocket (live updates) | REST gives full data on page load; WS delta for live updates without polling |
| Action feedback mechanism | `ActionResult` stored in `Agent.last_action_result` | LLM prompt builder reads it from agent; reset after read (1-tick lifespan) |
| Orphan adoption | Automatic (nearest adult) | Reliable, no LLM dependency for critical survival path |
| Trade rejection default | Rejection on LLM timeout | Safe default — never loses resources by accident |
| Childhood LLM | Children skip LLM entirely | Instinct-only movement near parent; LLM call is wasted on non-autonomous agent |

## Learnings

1. **Tick phase ordering matters**: Proximity-based social interactions had to come AFTER FSM execution but BEFORE snapshot building. Getting the ordering wrong caused agents to act on stale social context.

2. **Action feedback lifespan is critical**: Keeping `last_action_result` alive for exactly one tick and clearing it after prompt consumption prevents stale context accumulation. Multiple tests caught edge cases where timeouts would retain old state.

3. **Conversation spam is real**: Even with 5 pairs/tick cap, the O(n²) proximity check for 20 agents generates 190 pairs. The `_pending_pairs` deferral mechanism was essential to prevent tick loop slowdown.

4. **Knowledge sharing during encounters is elegant**: The `detect_encounters()` method automatically shares knowledge from knowledgeable agents to ignorant ones via `share_knowledge` messages. This creates emergent information diffusion without explicit LLM intervention.

5. **Faction colors on canvas**: The approach of resolving faction color in `updateFromSnapshot()` via a lookup dict avoids coupling the canvas renderer to the faction manager. Clean separation of concerns.

6. **Child stat inheritance**: Using `parent.stat ± random(0, 15)` with clamp to [0, 100] creates natural variation while keeping stats in valid range. The ±15 window ensures children are similar but not identical to parents.

7. **Trade atomicity**: The two-phase trade (proposal → evaluation → execution) required careful state management across ticks. The proposer's resources must remain locked during evaluation, or a race condition could allow double-spending.

## Next Steps

1. **Add ChromaDB persistence for agent memory** — Currently agent memory is in-memory only. ChromaDB would enable long-term memory across sessions and richer LLM context.

2. **Faction leadership hierarchy** — Currently factions are flat. Adding leader/follower roles, elections, or emergent leadership would increase depth.

3. **Natural language conversations** — The structured message format works well, but NL generation would make conversations more engaging and varied.

4. **Territory/ownership system** — Agents could claim territory, build structures, and defend resources, creating more complex faction dynamics.

5. **Performance optimization** — The O(n²) proximity check could be optimized with spatial partitioning (grid cells) for larger populations.

6. **War/conflict system** — Faction vs faction conflict, resource raids, and defensive behaviors would complete the societal model.

7. **Colony panel enhancements** — Add charts for population trends over time, resource production/consumption rates, and faction influence metrics.
