## Exploration: FSM Stability and Refactor

### Current State

The simulation engine runs a synchronous FSM per agent inside an async tick loop (10 ticks/sec). The FSM has 6 states: `idle` → `evaluate` → {`moving`, `executing`, `llm_trigger`} → `llm_waiting`. Director mode hijacks `_fsm_evaluate()` at the START — if a command is queued for the agent, it short-circuits the normal evaluation and executes the command instead.

The LLM integration has TWO processing paths:
1. **FSM path**: `_fsm_llm_waiting()` directly checks `agent.llm_future.done()` and processes the result
2. **Poll path**: `_poll_llm_responses()` calls `self.llm.poll_completed()` which drains completed futures from the orchestrator's `_pending` dict

These two paths compete for the same future objects — the future lives in BOTH `agent.llm_future` AND `self.llm._pending[agent_id]`.

### Fragile Points (ordered by severity)

#### CRITICAL

**F1. Dual-path LLM response processing (engine.py:1497-1539 vs 1600-1631)**

The same LLM future is accessible through TWO channels: `agent.llm_future` (consumed by `_fsm_llm_waiting` at line 1508) and `self.llm._pending[agent_id]` (consumed by `poll_completed()` at line 1602). The guard `agent.llm_call_pending` prevents double-processing only if the agent is still in `llm_waiting` when the poll path runs.

**The race**: If `_fsm_llm_waiting` processes the future during step 2 (FSM), the agent transitions to `evaluate`. Then at step 4 (`_poll_llm_responses`), `poll_completed()` returns the SAME future from `_pending`. The guard `not agent.llm_call_pending` is True (already set to False by `_fsm_llm_waiting`) → skip. This works but is wasteful.

**The real danger**: If the agent was NOT in `llm_waiting` (e.g., director command or health interruption forced it out), the poll path is the ONLY handler. But if the agent re-enters `llm_waiting` in the same tick and the future completes between FSM step 2 and poll step 4, BOTH paths could process it. More critically, if `_poll_llm_responses` processes a response for an agent that has SINCE been given a director command (which cleared `llm_call_pending`), the poll path will apply the LLM plan over the director's intent.

```python
# Timeline of the race:
Tick N:
  Step 2 (FSM): agent in llm_waiting, future.done()=False → evaluate (stays in llm_waiting via instinct)
  Step 4 (Poll): future.done()=True → poll_completed returns it → llm_call_pending=True → applies plan!
  # But agent is now in executing from instinct path — plan conflicts
```

**F2. LLM future cancellation leaks background tasks (orchestrator.py:194-248, engine.py:1078-1081)**

When a director command cancels `agent.llm_future` (engine.py:1080), the corresponding `_resolve()` coroutine in both `MockLLMOrchestrator` and `RealLLMOrchestrator` is STILL RUNNING as a background task. It will:
- In `RealLLMOrchestrator`: acquire the semaphore (blocking other agents!), make the HTTP call, then hit `if not future.done()` guard and discard the result
- In `MockLLMOrchestrator`: sleep for `random.uniform(0.5, 2.0)` seconds, then hit the same guard

With `RealLLMOrchestrator` having `_llm_semaphore = Semaphore(1)`, ONE cancelled agent can block ALL other agents from making LLM calls for up to 30+ seconds (the HTTP timeout).

```python
# orchestrator.py:194-248
async def _resolve() -> None:
    async with self._llm_semaphore:  # Blocks ALL other agents!
        result = await self._call_ollama(prompt)  # 30s timeout
    # 30 seconds later...
    if not future.done():  # True! future was cancelled but not "done"
        future.set_result(result)  # Sets result on a cancelled future! No error.
```

Wait — `future.cancel()` in Python DOES mark the future as done. So `if not future.done()` returns False, and the result is silently discarded. But the damage (30s semaphore hold + wasted HTTP call) is done.

**F3. Cooldown ping-pong between llm_trigger and llm_waiting (engine.py:1480-1485, 1497-1504)**

When the LLM cooldown is active (tick - last < 30):
1. `_fsm_llm_trigger` (line 1482): transitions to `llm_waiting` WITHOUT setting a future
2. `_fsm_llm_waiting` (line 1500): sees `agent.llm_future` is None → transitions to `evaluate`
3. `_run_survival_chain` (line 1009): no plan, no LLM pending → triggers `llm_trigger` again
4. Goto 1 — repeats every tick for up to 30 ticks

Each cycle re-evaluates `_fsm_evaluate` (food/water checks, role priorities, survival chain), so it's not completely frozen. But it burns CPU and generates a no-op transition storm. If the cooldown logic was meant to limit LLM calls, it achieves that — at the cost of 30 unnecessary FSM cycles per agent.

#### HIGH

**F4. Director command queue overwrites silently (engine.py:103, ws.py:77)**

`engine.command_queue[agent_id]` is a single slot per agent — LAST WRITE WINS. Two rapid commands for the same agent (e.g., `move_to` then `do_action`) silently lose the first. There's no queueing, no timestamp ordering. The command_dispatcher in ws.py writes directly:

```python
engine.command_queue[agent_id] = {"type": command_type, "payload": cmd_payload}
```

If the UI sends commands faster than the tick rate (10Hz), commands are dropped. The user gets no feedback that their first command was overwritten.

**F5. `release_all` incomplete reset (engine.py:1135-1137)**

`release_all` clears `command_queue` and sets `director_mode = False`. But it does NOT:
- Cancel pending LLM futures
- Clear agent `active_plan` or `plan_step_index`
- Reset agent `current_action`, `target_position`, or `move_path`
- Clear `injected_thoughts`
- Reset LLM cooldown (`_last_llm_tick`)

This means: if a user set a plan via director mode, then `release_all`, the agent continues executing the old plan. The "release" from director control is incomplete.

**F6. Partner FSM mutation during reproduction (engine.py:1001-1005)**

When an agent initiates reproduction, `_run_survival_chain` directly modifies the partner's FSM:
```python
fsm_partner = self.fsms[partner.id]
if fsm_partner.current_state == "idle":
    fsm_partner.transition_to("evaluate")
if fsm_partner.current_state != "executing":
    fsm_partner.transition_to("executing")  # Can raise!
```

If the partner is in `llm_waiting` or `moving`, the second `transition_to("executing")` call will raise a `ValueError` (invalid transition). This exception is caught by the per-agent try/except in `_run_agent_fsm`, so it won't crash the tick, but the reproduction fails silently. This is a data corruption issue — the originating agent's `_is_reproducing` flag is not cleaned up.

**F7. `release` command doesn't stop director-controlled actions (engine.py:1131-1133)**

The `release` command pops the queue entry but does nothing else. If the agent is in `executing` (doing a director-ordered action) or `moving` (moving to a director-ordered position), it continues until the action/path completes before re-evaluating. The user expects "release" to immediately restore autonomy, but it only takes effect on the next evaluate cycle.

#### MEDIUM

**F8. `current_action_emoji` not cleared on action completion (engine.py:1456-1459)**

When `_fsm_executing` finishes an action:
```python
agent.action_progress = 0.0
agent.action_duration = 0
agent.current_action = None
# agent.current_action_emoji is NOT cleared!
```

The emoji persists across state transitions — the snapshot will show a stale emoji until the next action sets it. The director command `do_action` also doesn't set `current_action_emoji` (engine.py:1097-1113).

**F9. `_fsm_llm_waiting` instinct actions don't set all action fields consistently (engine.py:1541-1594)**

The instinct branch (lines 1541-1594) has multiple decision paths:
- Poison path (1549-1563): sets all 4 fields + transitions → OK
- Eat path (1566-1571): sets all 4 → OK
- Rest path (1573-1578): sets all 4 → OK
- Move path (1580-1594): sets action-related fields but the action* fields (action_duration, action_progress) are NOT reset — they retain values from the previous action
  - `current_action` is set to "seeking water"/"seeking food"
  - `current_action_emoji` is set
  - But `action_duration` and `action_progress` are NOT touched
  - The transition is to "moving", so `_fsm_moving` doesn't use these fields, but they leak into snapshots

**F10. `_poll_llm_responses` can overwrite a plan mid-execution (engine.py:1600-1631)**

If an agent is in `executing` or `moving` state when its LLM response arrives:
1. Agent started executing a plan step
2. LLM response completes — poll path processes it
3. `_poll_llm_responses` sets `agent.active_plan` to a brand new plan
4. The in-progress step belongs to the OLD plan
5. On next evaluate, `_run_survival_chain` reads from `agent.active_plan["steps"][agent.plan_step_index]`
6. `plan_step_index` was advanced for the old plan — may be out of bounds in the new plan!

The `plan_step_index` is not reset because `_poll_llm_responses` sets `plan_step_index = 0` — wait, it DOES set it to 0. So the plan is properly reset. But the current action continues with stale context. The agent finishes the current action (from the old plan), then the new plan starts from step 0 on next evaluate. This is actually OK but wasteful.

#### LOW

**F11. `_fsm_moving` collision avoidance can loop indefinitely (engine.py:1285-1299)**

If two agents are in adjacent occupied tiles and both try to nudge, they could enter a livelock where each tick they swap positions or nudge into each other. The collision avoidance doesn't have a backoff or random jitter — it always tries the same direction order `[(1,0), (-1,0), ...]`. Under high agent density, this can manifest as agents "stuttering" in place.

**F12. `_process_needs` iterates `self.agents` while modifying it (engine.py:546-677)**

When an agent dies, it's added to `dead_agents` and removed from `self.agents` AFTER the loop (line 672). This is safe because removal happens post-iteration. But `_agent_health[agent.id] = agent.health` on line 599 is set for agents that then get immediately processed for death — the health is updated before death processing confirms death. Minor correctness issue — doesn't affect behavior because the death processing reads `agent.health` directly, not from the cache.

### Affected Areas

| File | Lines | Issue |
|------|-------|-------|
| `backend/app/simulation/engine.py` | 1001-1005 | F6: Partner FSM mutation |
| `backend/app/simulation/engine.py` | 1078-1081 | F2: LLM future cancellation |
| `backend/app/simulation/engine.py` | 1097-1113 | F8: Missing emoji in do_action |
| `backend/app/simulation/engine.py` | 1135-1137 | F5: release_all incomplete |
| `backend/app/simulation/engine.py` | 1456-1459 | F8: emoji not cleared |
| `backend/app/simulation/engine.py` | 1474-1539 | F1+F3: Dual-path + cooldown ping-pong |
| `backend/app/simulation/engine.py` | 1497-1539 | F1+F9: Dual-path + instinct fields |
| `backend/app/simulation/engine.py` | 1600-1631 | F1+F10: Poll path overwrites plans |
| `backend/app/simulation/engine.py` | 1285-1299 | F11: Collision avoidance livelock |
| `backend/app/ai/orchestrator.py` | 194-248 | F2: Cancelled future background leak |
| `backend/app/simulation/agent.py` | 447-564 | F2: MockLLM future cancellation |
| `backend/app/api/ws.py` | 77 | F4: Command queue overwrite |
| `backend/app/simulation/actions.py` | 1054-1101 | F8: Action durations depend on mutable state |

### Approaches

1. **A: Unify LLM response processing** — Eliminate the dual path
   - Remove `_poll_llm_responses` entirely
   - All LLM responses flow through `_fsm_llm_waiting` ONLY
   - Future is removed from `_pending` via a callback when attached to `agent.llm_future`
   - Pros: Eliminates F1 and F10 entirely; single source of truth; simpler
   - Cons: Poll path was added for a reason (agents not in llm_waiting when response arrives); would need a state-independent handler
   - Effort: Medium
   - Dependencies: Must add a fallback mechanism for agents that left `llm_waiting` before response arrived

2. **B: Handle all LLM responses in poll path, not in FSM** — Reverse the architecture
   - `_fsm_llm_trigger` fires the LLM call and transitions to `llm_waiting`
   - `_fsm_llm_waiting` ONLY handles instinct (no result processing)
   - `_poll_llm_responses` is the SOLE result handler for ALL agents
   - Pros: Eliminates F1 cleanly; poll path already has the state guard
   - Cons: Poll path runs after FSM — agents stay in `llm_waiting` one tick longer; changes existing behavior
   - Effort: Low

3. **C: Cancel background task, not just the future** — Proper cancellation
   - Track the background asyncio.Task along with the future (store it on agent or in orchestrator)
   - When cancelling LLM, cancel BOTH the future AND the task
   - In `RealLLMOrchestrator`, wrap `_resolve()` in a `try/finally` that releases the semaphore
   - Pros: Eliminates F2 resource leak; semaphore contention resolved
   - Cons: Requires tracking tasks per agent; more state
   - Effort: Medium

4. **D: Proper command queueing** — One queue per agent, not a single slot
   - Replace `command_queue: dict[str, dict]` with `command_queue: dict[str, list[dict]]`
   - Process one command per evaluate, drain FIFO
   - Add timestamp to commands for ordering
   - Pros: Eliminates F4; better UX; no silent drops
   - Cons: More complex; commands can pile up; needs TTL or max queue size
   - Effort: Medium

5. **E: Complete release_all reset** — Full state restoration
   - Cancel pending LLM futures
   - Clear `active_plan`, `plan_step_index`, `current_action`, `target_position`, `move_path`
   - Clear `injected_thoughts`
   - Reset `_last_llm_tick` to force fresh evaluation
   - Force FSM to `evaluate` for all agents
   - Pros: Eliminates F5; predictable behavior after release
   - Cons: More work per release; could lose user-desired state
   - Effort: Low

6. **F: Remove partner FSM mutation** — Let reproduction flow through evaluate naturally
   - Instead of forcing partner to `executing`, just set partner's reproduction flags and let their OWN FSM pick it up on their next evaluate
   - The partner will naturally transition through their own FSM next tick
   - Pros: Eliminates F6; removes cross-agent state mutation; safer
   - Cons: One-tick delay in partner starting reproduction
   - Effort: Low

7. **G: Add cooldown guard at FSM entry** — Prevent the ping-pong loop
   - In `_run_agent_fsm`, if agent is in `llm_trigger` and cooldown is active, skip directly to `evaluate` (bypass `_fsm_llm_trigger` entirely)
   - Or: add a timer field `_llm_cooldown_until` that prevents entering `llm_trigger` state at all
   - Pros: Eliminates F3; saves CPU cycles
   - Cons: Slight change in when LLM retries happen
   - Effort: Low

8. **H: Defensive action field reset** — Consistent reset of all action fields
   - Always reset `current_action`, `current_action_emoji`, `action_duration`, `action_progress` together as an atomic group
   - Create a helper method `_reset_action_state(agent)` to ensure consistency
   - Set `current_action_emoji` in `do_action` director command
   - Pros: Eliminates F8, F9; prevents snapshot inconsistencies
   - Cons: None
   - Effort: Low

9. **I: Collision avoidance with jitter** — Add random backoff
   - Shuffle the nudge direction order randomly each tick
   - Add a max-tries counter before skipping movement for that tick
   - Pros: Eliminates F11; handles high-density scenarios better
   - Cons: Agents still may not make progress under extreme density
   - Effort: Low

10. **J: Prevent plan overwrite in poll path** — Guard against stale plan replacement
    - `_poll_llm_responses` should only update `active_plan` if the agent is in `llm_waiting` or `evaluate` state
    - Skip if agent is in `executing` or `moving`
    - The plan will be picked up on the next `evaluate` cycle
    - Pros: Mitigates F10; prevents plan corruption
    - Cons: Slight delay in plan application; need to prevent `_pending` from growing stale
    - Effort: Low

### Recommendation

Implement in this order of priority:

1. **P0 — Fix the dual-path LLM race (Approach B):** Remove result processing from `_fsm_llm_waiting`, make `_poll_llm_responses` the sole handler. This is the most dangerous issue and touches the fewest lines.

2. **P0 — Cancel background tasks properly (Approach C):** Track the background task alongside the future. Cancel both when a director command preempts the LLM. Protect the semaphore with try/finally.

3. **P1 — Complete `release_all` reset (Approach E):** Ensure `release_all` cancels pending LLM calls and clears agent plan state, not just the command queue.

4. **P1 — Remove partner FSM mutation (Approach F):** Let reproduction flow naturally through each agent's own FSM evaluation.

5. **P1 — Add cooldown guard (Approach G):** Prevent the llm_trigger/llm_waiting ping-pong loop by checking cooldown before entering `llm_trigger`.

6. **P2 — Defensive action field reset (Approach H):** Create a helper for consistent action field management. Always clear emoji on action end and set it on `do_action`.

7. **P2 — Poll path guard (Approach J):** Only apply new plans when agent is in an appropriate state.

8. **P3 — Command queueing (Approach D):** Add proper per-agent command queues. Lower priority because the current behavior is at least deterministic.

9. **P3 — Collision jitter (Approach I):** Low priority — only manifests under high agent density.

### Risks

1. **Removing `_fsm_llm_waiting` result processing** could delay plan application by one tick for agents whose LLM response arrives during the FSM step. This is acceptable and safer than the current race.

2. **Task tracking** adds memory pressure per-agent. With hundreds of agents, storing one extra reference is negligible.

3. **Command queueing** changes the WebSocket protocol behavior — the frontend must handle queue acknowledgment. Without it, users get silent queueing instead of silent overwrites. Either way is silent without feedback.

4. **Any refactor of `_fsm_evaluate`** must preserve the director-mode early-return at line 1150. This is the single integration point between two systems.

5. **Changing reproduction flow** may break existing tests that expect immediate partner reaction. The one-tick delay is semantically correct but may surface in observable behavior.

6. **`release_all` clearing plans** could frustrate users who set plans and then use `release_all` expecting the plans to survive. Need to decide: does `release_all` mean "release from director control" or "reset to factory defaults"? Current behavior (incomplete reset) means neither — it's ambiguous.

7. **Frontend dependency**: If dual-path removal changes snapshot timing for LLM plans, the frontend's "thinking" indicator (`last_thought = "Waiting for guidance..."`) may flash differently. Low risk but worth noting.

### Ready for Proposal

**Yes.** The exploration is complete with 12 fragility points identified, 10 approaches to fix them, and a clear priority ordering. The proposal phase should select a subset of P0/P1 fixes for the first iteration and defer P2/P3 to follow-ups.

### Artifacts

- **Engram**: `sdd/fsm-stability-and-refactor/explore`
- **Filesystem**: `openspec/changes/fsm-stability-and-refactor/exploration.md`
