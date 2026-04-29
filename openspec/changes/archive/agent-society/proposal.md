# Proposal: Agent Society

## Intent

Agents survive independently, asocially — no bonds, no trade, no childhood, no factions, no knowledge sharing. This change builds a full social simulation layer: relationships, conversations, trade, childhood dependency, factions, limited perception, LLM action feedback, and colony-level UI.

## Scope

### In Scope (8 features)
- **F1 — LLM action feedback**: LLM receives action results as context for next decision
- **F2 — Limited perception**: Resource subtypes with hidden properties (poisonous vs safe berries), learned by experience or conversation
- **F3 — Childhood**: Infants depend on caregivers for food/water; stats influenced by parents
- **F4 — Factions**: Social groups with shared identity and resource pool
- **F5 — Trade**: Resource exchange between nearby agents (TRADE action)
- **F6 — Socialization**: Messages, information sharing, coordination (SOCIALIZE action)
- **F7 — Colony Info panel**: Backend endpoint + frontend panel with demographics and total resources
- **F8 — Relationship-based reproduction**: Agents need N interactions before REPRODUCE is allowed

### Out of Scope
- Territory/ownership, faction leadership hierarchy, war/combat
- ChromaDB persistence for agent memory (deferred)
- Natural language generation for conversations (structured messages only)

## Capabilities

### New Capabilities
- `agent-society`: Full social simulation — relationships, factions, childhood dependency, trade, limited perception, LLM action feedback, and conversation system.

### Modified Capabilities
- `simulation-engine`: Extended Agent model (relationships, faction, childhood state, knowledge), new action types (TRADE, SOCIALIZE), resource subtypes with hidden properties, new FSM states for infant and social interactions.

## Approach

Five-phase incremental build, each independently testable:

### Phase 1: Foundation (F1 + F8)
Relationship tracking on Agent (`interaction_count`, `relationship_scores: dict[str, float]`). LLM `decide_next_action()` receives result of completed action as context. REPRODUCE gated by `interaction_count >= threshold`.

### Phase 2: Social Core (F6)
SOCIALIZE action type. `MessageQueue` per agent (FIFO, max N). Proximity-based conversation trigger in tick loop. In-memory knowledge store (dict of `{resource_type: {property: value}}`).

### Phase 3: Society (F2 + F5)
Resource subtypes (`POISONOUS_BERRY`, `SAFE_BERRY`) with hidden `is_poisonous` property. Knowledge propagation via SOCIALIZE. TRADE action: offer/accept exchange between adjacent agents.

### Phase 4: Lifecycle & Groups (F3 + F4)
Infant FSM state — cannot eat/drink, decays hunger/thirst faster, needs caregiver within radius. Caregiver assigned at birth (parent or nearest adult). Faction model (`id`, `name`, `member_ids`, `shared_inventory: dict`), join/leave CRUD.

### Phase 5: Colony UI (F7)
Backend `GET /api/colony` endpoint returning demographics (population, age distribution, factions) and total resources. `ColonyInfo.svelte` frontend panel. HUD widgets showing key metrics.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/simulation/agent.py` | Modified | relationships, faction_id, infant_state, knowledge fields |
| `backend/app/simulation/actions.py` | Modified | TRADE, SOCIALIZE added; REPRODUCE gated |
| `backend/app/simulation/engine.py` | Modified | New tick phases, proximity triggers for conversation/trade |
| `backend/app/simulation/world.py` | Modified | Resource subtypes with hidden properties |
| `backend/app/simulation/knowledge.py` | New | Perception/learning store per agent |
| `backend/app/simulation/faction.py` | New | Faction model + CRUD |
| `backend/app/simulation/conversation.py` | New | Message queue + social interaction logic |
| `backend/app/api/colony.py` | New | Colony stats endpoint |
| `frontend/src/lib/components/ColonyInfo.svelte` | New | Demographics panel |
| `frontend/src/lib/stores/simulationStore.svelte.js` | Modified | New social/colony data in snapshot |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM latency with chained action feedback | Med | Async non-blocking; timeout → fallback instinct behavior |
| Conversation spam slows tick loop | Low | Cap conversations/tick; FIFO max 50 per agent |
| Infants die before caregiver arrives | Med | Always spawn adjacent to parent; fail-safe autofeed timer |
| Faction imbalance (one dominant) | Low | Soft membership caps; emergent dynamics, not enforced |

## Rollback Plan

Revert `agent.py`, `actions.py`, `engine.py`, `world.py`, `simulationStore.svelte.js` to last stable commit. Delete new modules: `knowledge.py`, `faction.py`, `conversation.py`, `colony.py`, `ColonyInfo.svelte`. No DB migrations.

## Dependencies

- All phases depend on existing `simulation-engine` (tick loop, actions, FSM, world grid)
- Phase 3 (knowledge) depends on Phase 2 (conversations)
- Phase 4 (childhood) depends on Phase 1 (relationship-based reproduction)

## Success Criteria

- [ ] Agents perform 8+ action types (TRADE and SOCIALIZE added)
- [ ] Relationship score gates reproduction (threshold interactions verified)
- [ ] LLM receives prior action result as context in next decision
- [ ] Agents discover hidden resource properties via consumption and conversation
- [ ] Infant agents survive only when caregiver is within range
- [ ] Factions form with shared resource pools
- [ ] Colony panel shows demographics and total resource counts
- [ ] All new and existing engine tests pass
