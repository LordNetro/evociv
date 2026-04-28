# Tasks: Agent Lifecycle and UI

## Phase 1: Backend Data Model

- [ ] 1.1 T1 — Add `age: int = 0`, `max_age: int = randint(2000,5000)`, `sex: str = random.choice(["male","female"])` to Agent dataclass — `backend/app/simulation/agent.py` — deps: none — S
- [ ] 1.2 T2 — Pass `sex`/`age`/`max_age` in `AgentFactory.from_config` and `create_default_agents` — `backend/app/simulation/agent.py` — deps: T1 — S
- [x] 1.3 T3 — Add `REPRODUCE = "reproduce"` to `ActionType` enum — `backend/app/simulation/actions.py` — deps: none — S
- [x] 1.4 T4 — Register REPRODUCE in `REGISTRY` (stub handler), `get_action_duration` (10 ticks), `ACTION_EMOJIS` ("❤️") — `backend/app/simulation/actions.py` — deps: T3 — S
- [ ] 1.5 T5 — Add `sex`, `age`, `max_age`, `strength`, `intelligence`, `sociability`, `speed`, `system_prompt`, `monologue_history` to `AgentState` — `backend/app/models/schemas.py` — deps: none — S
- [ ] 1.6 T6 — Serialize new fields in `_build_agent_state`; truncate `system_prompt` to 200 chars — `backend/app/simulation/snapshot.py` — deps: T5 — S

## Phase 2: Engine Logic

- [x] 2.1 T7 — Increment `agent.age` each tick in `_process_needs`; kill agent when `age >= max_age` (death cause: "old_age") — `backend/app/simulation/engine.py` — deps: T1 — M
- [x] 2.2 T8 — Implement `_find_reproduction_partner(agent)` — find nearby agent of opposite sex with `age > 500` — `backend/app/simulation/engine.py` — deps: T1 — M
- [x] 2.3 T9 — Implement `_create_offspring(parent_a, parent_b)` — create new Agent with inherited attributes, random position, age=0 — `backend/app/simulation/engine.py` — deps: T1, T8 — M
- [x] 2.4 T10 — Add reproduction trigger in `_fsm_evaluate` — when agent has partner nearby, set action to REPRODUCE — `backend/app/simulation/engine.py` — deps: T3, T8 — M
- [x] 2.5 T11 — Complete reproduction in `_fsm_executing` — call `_create_offspring`, call `add_agent`, push birth event — `backend/app/simulation/engine.py` — deps: T9, T10, T13 — M
- [x] 2.6 T12 — Implement `add_agent(agent)` method on engine — register FSM, add to agents list, mark dirty — `backend/app/simulation/engine.py` — deps: none — S

## Phase 3: Events

- [ ] 3.1 T13 — Create `create_birth_event(agent, parents, tick)` helper → SimEvent with type "birth" — `backend/app/simulation/event_queue.py` — deps: none — S
- [ ] 3.2 T14 — Update `create_death_event` to accept optional `cause: str` param and include it in description — `backend/app/simulation/event_queue.py` — deps: none — S

## Phase 4: Frontend

- [ ] 4.1 T15 — Redesign `AgentInspector.svelte` with collapsible sections: Vital Signs, Identity, Attributes, Inventory, Monologue, System Prompt — `frontend/src/lib/components/AgentInspector.svelte` — deps: T5 (schema) — M

## Phase 5: Tests

- [ ] 5.1 T16 — Test age increments each tick and death by old age — `backend/tests/test_engine.py` — deps: T7 — M
- [ ] 5.2 T17 — Test reproduction flow: partner detection, offspring creation, birth event — `backend/tests/test_engine.py` — deps: T8, T9, T11, T13 — M
- [ ] 5.3 T18 — Test new snapshot fields (sex, age, max_age, attributes, system_prompt truncation) — `backend/tests/test_engine.py` — deps: T6 — S
- [ ] 5.4 T19 — Test `create_death_event` with cause param — `backend/tests/test_engine.py` — deps: T14 — S
