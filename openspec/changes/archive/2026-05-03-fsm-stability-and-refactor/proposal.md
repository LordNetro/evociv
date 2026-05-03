# Proposal: FSM Stability and Refactor

## Intent

The simulation engine's FSM has 12 identified fragility points that cause agents to get stuck in states, race conditions in LLM response processing, resource leaks from cancelled futures, and incomplete state resets. These manifest as agents that stop responding to director commands, fail to execute plans, or behave erratically after director mode interactions.

The core problems are:

1. **Race condition**: Two code paths (`_fsm_llm_waiting` and `_poll_llm_responses`) compete to process the same LLM future, with guards that are too weak to prevent double-processing when states change mid-tick.
2. **Resource leaks**: Cancelling an LLM future does not cancel the underlying background task, which continues to hold the semaphore and waste HTTP calls.
3. **Incomplete resets**: `release` and `release_all` don't fully restore agent autonomy — plans, actions, and positions persist after "release."
4. **State corruption**: Cross-agent FSM mutation during reproduction and inconsistent action field management produce silent failures and stale snapshot data.

## Scope

### IN SCOPE — This Iteration (8 fixes)

| ID | Issue | Approach | Priority |
|----|-------|----------|----------|
| F1 | Dual-path LLM response processing race | **B**: Remove result processing from `_fsm_llm_waiting`, make `_poll_llm_responses` sole handler | **P0** |
| F2 | LLM future cancellation leaks background tasks | **C**: Cancel background task too, protect semaphore with try/finally | **P0** |
| F3 | Cooldown ping-pong between llm_trigger and llm_waiting | **G**: Check cooldown before entering `llm_trigger` | **P1** |
| F5 | `release_all` incomplete reset | **E**: Full state reset — cancel LLM, clear plans, actions, paths, thoughts | **P1** |
| F6 | Partner FSM mutation during reproduction | **F**: Remove cross-agent mutation, let reproduction flow naturally | **P1** |
| F7 | `release` doesn't stop current action | **E**: Release stops current action and plan, forces re-evaluate | **P1** |
| F8 | Missing emoji in `do_action` + not cleared on action end | **H**: Set emoji in `do_action`, clear all action fields as atomic group | **Include** |
| F9 | Instinct actions field inconsistency (action_duration/action_progress not reset) | **H`: Create `_reset_action_state()` helper for consistent field management | **Include** |

### DEFERRED — Future Iteration (4 points)

| ID | Issue | Approach | Priority | Rationale |
|----|-------|----------|----------|-----------|
| F4 | Command queue overwrites silently | **D**: Per-agent command queues | P2 | Requires WS protocol change; not a correctness bug (deterministic) |
| F10 | Poll path plan overwrite mid-execution | **J**: Guard plan application by state | P2 | Partially mitigated by F1 fix (single path) |
| F11 | Collision avoidance livelock | **I**: Add random jitter to nudge order | P3 | Only manifests under high agent density |
| F12 | Health cache minor inconsistency | — | P3 | No observable behavior change |

## Approach

### F1: Eliminate Dual-Path LLM Response Processing (Approach B)

**What**: Remove result processing from `_fsm_llm_waiting`. This method will only handle instinct decisions (what to do while waiting). The `_poll_llm_responses` method becomes the **sole** handler for all completed LLM responses, regardless of agent state.

**Rationale**:
- Eliminates the race condition at its root — one future, one consumer
- The poll path already has state guards (`agent.llm_call_pending`) and runs after the FSM loop
- Changes fewer lines than Approach A (which would require adding a new callback mechanism)
- The one-tick delay in plan application (until poll runs) is acceptable and safer than racing

**Changes in `_fsm_llm_waiting` (engine.py:1497-1539)**:
- Remove the `if agent.llm_future and agent.llm_future.done()` block (result processing)
- Keep only the instinct decision logic (lines 1541+)
- If no future is pending and cooldown is active, transition to `evaluate` (as before)

**No changes needed in `_poll_llm_responses` (engine.py:1600-1631)**:
- It already handles all states correctly via `llm_call_pending` guard
- After this change, it will be the ONLY path that applies LLM responses

---

### F2: Cancel Background Tasks Properly (Approach C)

**What**: Track the asyncio.Task alongside the future. When cancelling an LLM call, cancel BOTH the future AND the background task. Protect the semaphore with try/finally.

**Changes in `orchestrator.py`**:
- Add `_pending_tasks: dict[str, asyncio.Task]` — maps agent_id to the running `_resolve` task
- In `_resolve()`, store the task reference before calling: store `asyncio.current_task()` in `_pending_tasks[agent_id]`
- Wrap the semaphore `async with self._llm_semaphore:` in try/finally to ensure semaphore release even on cancellation
- Add method `cancel_agent_llm(agent_id)` that:
  1. Cancels the future (existing behavior)
  2. Cancels the task from `_pending_tasks` if present
  3. Removes from both dicts

**Changes in `engine.py` (line 1078-1081)**:
- Replace `agent.llm_future.cancel()` with `self.llm.cancel_agent_llm(agent_id)`
- This is called when director command preempts the agent's LLM call

**Changes in `MockLLMOrchestrator` (agent.py:447-564)**:
- Same pattern: track the background task in `_resolve()`

**try/finally in `_resolve()`**:
```python
async def _resolve(agent_id, prompt, future):
    task = asyncio.current_task()
    self._pending_tasks[agent_id] = task
    try:
        async with self._llm_semaphore:
            result = await self._call_ollama(prompt)
            if not future.done():
                future.set_result(result)
    except asyncio.CancelledError:
        pass  # Expected when we cancel the task
    finally:
        self._pending_tasks.pop(agent_id, None)
        # semaphore is released by async with, even on CancelledError
```

**Rationale**:
- `async with` already releases on CancelledError — but only if the CancelledError is raised *inside* the `async with` block. The task cancellation won't propagate until an await point. If `_call_ollama` never awaits (e.g., mock with `asyncio.sleep`), the CancelledError is raised at the `sleep` await.
- The try/finally ensures `_pending_tasks` cleanup regardless of cancellation timing.

---

### F3: Prevent Cooldown Ping-Pong (Approach G)

**What**: Check LLM cooldown BEFORE transitioning to `llm_trigger` state. If cooldown is active, skip `_fsm_llm_trigger` entirely and go to `evaluate`.

**Changes in `_run_agent_fsm` (engine.py, around FSM dispatch)**:
- Before calling `_fsm_llm_trigger`, check `self._last_llm_tick.get(agent.id, 0)` and compare with current tick
- If within cooldown period (30 ticks), skip to `evaluate` directly
- This prevents the cycle: `llm_trigger` → sets no future → `llm_waiting` → sees no future → `evaluate` → triggers `llm_trigger` again

**Alternative (simpler)**: Add the check inside `_fsm_llm_trigger` itself — if cooldown is active, just transition to `evaluate` and return immediately.

**Rationale**:
- Lowest effort change (2-3 lines)
- Doesn't change the cooldown logic itself, just prevents the wasteful loop
- The agent will still run `_run_survival_chain` via `evaluate`, so food/water needs are handled

---

### F5 & F7: Complete `release` and `release_all` Reset (Approach E)

**What**: Both `release` (single agent) and `release_all` (all agents) must fully reset agent state to restore autonomy. The current implementation only clears the command queue and director mode flag.

**Changes in `release` (engine.py:1131-1133)**:
After popping the command queue entry:
1. Cancel pending LLM future via `self.llm.cancel_agent_llm(agent_id)` (uses F2's new method)
2. Clear `agent.active_plan` and set `agent.plan_step_index = 0`
3. Clear `agent.current_action`, `agent.current_action_emoji`, `agent.action_progress`, `agent.action_duration`
4. Clear `agent.target_position` and `agent.move_path`
5. Clear `agent.injected_thoughts`
6. Reset `_last_llm_tick[agent_id]` to 0 (force fresh LLM evaluation)
7. Force FSM to `evaluate` state

**Changes in `release_all` (engine.py:1135-1137)**:
Same as above, applied to all agents, plus:
1. Set `self.director_mode = False` (existing)
2. Clear `self.command_queue` (existing)
3. Apply per-agent reset as above

**Rationale**:
- "Release" should mean "return to full autonomy" — that requires clearing director-imposed state
- A user who set elaborate plans and then uses `release_all` expects the agent to resume natural behavior
- If the user wants to preserve plans, they shouldn't call `release_all` (that's a training/UX issue, not a code issue)

---

### F6: Remove Partner FSM Mutation During Reproduction (Approach F)

**What**: Instead of directly modifying the partner's FSM state (which can raise `ValueError` if the transition is invalid), just set reproduction flags on the partner and let their own FSM pick it up naturally.

**Changes in `_run_survival_chain` (engine.py:1001-1005)**:
Replace:
```python
fsm_partner = self.fsms[partner.id]
if fsm_partner.current_state == "idle":
    fsm_partner.transition_to("evaluate")
if fsm_partner.current_state != "executing":
    fsm_partner.transition_to("executing")
```
With:
```python
# Signal partner to reproduce on their next evaluate cycle
partner._reproduce_requested = True
partner._reproduction_source = agent.id
```

Then in the partner's `_fsm_evaluate` (or the main dispatch), check `agent._reproduce_requested` and handle reproduction during the partner's own FSM cycle.

**Rationale**:
- Eliminates cross-agent state mutation entirely
- The partner naturally flows through their own FSM transitions
- One-tick delay is semantically correct — the partner "notices" the reproduction request on their next tick
- No more silent `ValueError` exceptions caught by the per-agent try/except

---

### F8 & F9: Defensive Action Field Reset (Approach H)

**What**: Create a `_reset_action_state(agent)` helper that atomically clears ALL action-related fields. Use it consistently across all code paths that start or end actions. Set `current_action_emoji` in `do_action`.

**New helper method**:
```python
def _reset_action_state(self, agent):
    agent.current_action = None
    agent.current_action_emoji = None
    agent.action_progress = 0.0
    agent.action_duration = 0
```

**Changes in `_fsm_executing` on action end (engine.py:1456-1459)**:
- Replace individual field resets with `_reset_action_state(agent)`

**Changes in `do_action` director command (engine.py:1097-1113)**:
- Add `agent.current_action_emoji = action_emoji` when setting `current_action`

**Changes in instinct move paths (engine.py:1541-1594, move path at 1580-1594)**:
- Call `_reset_action_state(agent)` before setting the move-specific fields
- This ensures `action_duration` and `action_progress` are always clean

**Rationale**:
- Single source of truth for action state lifecycle
- Eliminates stale emoji in snapshots (F8)
- Eliminates leaking `action_duration`/`action_progress` from previous actions (F9)
- Minimal change surface, high consistency gain

## Rollback Plan

Each fix is independent and can be reverted individually. The overall rollback strategy:

| Fix | Rollback | Risk |
|-----|----------|------|
| **F1** | Restore `_fsm_llm_waiting` result processing block. Git revert of the changes to `engine.py` lines 1497-1539. | Low — fully isolated change |
| **F2** | Remove `_pending_tasks` tracking, restore direct `agent.llm_future.cancel()`. Git revert of `orchestrator.py` and agent.py changes. | Medium — orchestrator.py changes may touch several methods |
| **F3** | Remove the cooldown guard from `_run_agent_fsm` or `_fsm_llm_trigger`. Git revert of 2-3 lines. | Low — minimal change |
| **F5+F7** | Restore old `release`/`release_all` implementation. Git revert of engine.py changes. | Low — isolated to these two methods |
| **F6** | Restore partner FSM mutation code. Git revert of the reproduction block in `_run_survival_chain`. | Low — isolated change |
| **F8+F9** | Remove `_reset_action_state` calls, restore individual field assignments. Git revert. | Low — no behavioral change, only data consistency |

**General rollback**: `git revert <commit>` for each fix's commit, in reverse order (apply after spec, design, verify).

## Risks

| Fix | Risk | Mitigation |
|-----|------|------------|
| **F1** | Agents stay in `llm_waiting` one tick longer (plan only applied during poll step, after FSM). | Acceptable: one tick (100ms) delay vs. race condition. Verify in tests that the delay doesn't cascade. |
| **F1** | If `_poll_llm_responses` is ever removed or refactored, LLM responses stop being processed entirely. | Add a comment linking `_fsm_llm_waiting` → `_poll_llm_responses` dependency. Consider adding a defensive assertion. |
| **F2** | Task tracking adds per-agent state. | Negligible — one dict lookup per agent. |
| **F2** | `asyncio.CancelledError` propagation may not work as expected on all Python async constructs. | Test with mock orchestrator that the task is actually cancelled and semaphore is released. |
| **F3** | Cooldown could be checked incorrectly (off-by-one tick). | Simple: `tick - last > cooldown` — test at boundary values. |
| **F5+F7** | `release_all` clearing plans surprises users who expected plans to persist. | This is the CORRECT behavior — "release" means return to autonomy. Document in API. |
| **F6** | One-tick delay in partner reproduction. | Semantically correct — the partner "notices" next tick. Update any tests that assert immediate partner reaction. |
| **F6** | New `_reproduce_requested`/`_reproduction_source` flags need to be serializable if agent state is persisted. | Add to agent serialization schema if persistence is used. |
| **F8+F9** | No behavioral risk — only snapshot consistency. | None. |
| **General** | Changes touch core simulation loop timing. | Run existing test suite after each fix. The backend has 114 tests. |

## Affected Areas

| File | Lines | Fixes |
|------|-------|-------|
| `backend/app/simulation/engine.py` | ~50 lines changed across: `_run_agent_fsm` (F3), `_fsm_llm_waiting` (F1), `_fsm_llm_trigger` (F3), `_fsm_executing` (F8), `_run_survival_chain` (F6), `release` (F7), `release_all` (F5), `do_action` (F8), instinct move (F9), new `_reset_action_state` helper (F8+F9) | F1, F3, F5, F6, F7, F8, F9 |
| `backend/app/ai/orchestrator.py` | `_resolve()` method, new `_pending_tasks` dict, new `cancel_agent_llm()` method | F2 |
| `backend/app/simulation/agent.py` | MockLLMOrchestrator `_resolve()` method | F2 |

### Files NOT Changed (Deferred)

| File | Reason |
|------|--------|
| `backend/app/api/ws.py` | F4 (command queue) deferred — would change WS protocol |
| `backend/app/simulation/actions.py` | F12 (health cache) — no observable issue |

## Execution Order

1. **F2 first** (orchestrator.py + agent.py) — the `cancel_agent_llm` method is a dependency for F5/F7
2. **F1** (engine.py) — the most critical fix, but needs to be tested after F2
3. **F3** (engine.py) — independent, low effort
4. **F5 + F7** (engine.py) — depends on F2's `cancel_agent_llm`
5. **F6** (engine.py) — independent, low effort
6. **F8 + F9** (engine.py) — last, safest changes

This order minimizes merge conflicts and ensures each fix can be tested independently.
