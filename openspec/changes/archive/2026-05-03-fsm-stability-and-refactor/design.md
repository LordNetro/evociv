# Design: FSM Stability and Refactor

## Technical Approach

Eight independent fixes targeting the simulation engine's FSM — race conditions
in LLM response processing (F1), background task resource leaks (F2),
wasteful cooldown cycles (F3), incomplete state resets (F5/F7),
cross-agent state corruption during reproduction (F6), and inconsistent
action field management (F8/F9). Each fix is isolated and independently
revertible. Execution order: F2 (orchestrator API dependency) → F1 (critical
race) → F3, F5+F7, F6, F8+F9 (independent, any order).

## Architecture Decisions

### D1: Poll Path Becomes Sole LLM Response Handler

**Choice**: Remove result processing from `_fsm_llm_waiting()`. All completed
LLM futures are handled exclusively by `_poll_llm_responses()`.

**Alternatives**: (A) Remove poll path, add callback-based fallback in FSM path.
Requires new state-independent handler and more invasive changes.

**Rationale**: The poll path already has state guards (`llm_call_pending`) and
runs AFTER the FSM loop (step 4 in `_tick()`). Removing the `done()` block
from `_fsm_llm_waiting` (lines 1506-1539) eliminates the race at its root —
one future, exactly one consumer. The one-tick delay in plan application
(plan applied at poll step instead of FSM step) is safer than racing.

**Consequence**: `_poll_llm_responses` must also transition agents from
`llm_waiting` to `evaluate` when a response is applied — currently it only
sets the plan without transitioning.

### D2: Track + Cancel Background Tasks via Orchestrator API

**Choice**: Add `_pending_tasks: dict[str, asyncio.Task]` to both
`RealLLMOrchestrator` and `MockLLMOrchestrator`. Add
`cancel_agent_task(agent_id)` method. In `_execute_director_command`, cancel
the future directly (preserves existing test contract) AND call
`self.llm.cancel_agent_task(agent.id)`.

**Rationale**: `future.cancel()` marks the future done but does NOT stop the
running `_resolve()` coroutine, which continues holding the semaphore and
wasting HTTP calls. `async with self._llm_semaphore` releases the semaphore
on `CancelledError` — but only if the task is actually cancelled. Tracking
tasks in the orchestrator (not on the `Agent` dataclass) keeps lifecycle
management where it belongs.

### D3: Cooldown Guard at FSM Dispatch

**Choice**: Check LLM cooldown in `_run_agent_fsm()` BEFORE dispatching to
`_fsm_llm_trigger`. If cooldown active, transition directly to `evaluate`.

**Rationale**: Current code checks cooldown INSIDE `_fsm_llm_trigger` and
transitions to `llm_waiting` without setting a future → `_fsm_llm_waiting`
sees no future → back to `evaluate` → survival chain triggers `llm_trigger`
again. This ping-pong wastes 2 FSM transitions per cooldown tick. Moving the
check to dispatch eliminates the `llm_waiting` detour entirely. Agent still
runs survival chain through `evaluate`, so food/water needs are still met.

### D4: Full State Reset on release/release_all

**Choice**: Both `release` and `release_all` cancel pending LLM futures+tasks,
clear `active_plan`, `plan_step_index`, `current_action`,
`current_action_emoji`, `action_duration`, `action_progress`,
`target_position`, `move_path`, `injected_thoughts`, and reset
`_last_llm_tick`. Single-agent `release` also transitions FSM to `evaluate`.

**Rationale**: "Release from director control" means "return to full autonomy."
Clearing all director-imposed state (plans, actions, positions) is the only
correct semantics. Current behavior (clear queue only) leaves agents executing
stale plans — which is neither "autonomous" nor "directed."

### D5: Flags-Only Reproduction Signaling

**Choice**: Set `_is_reproducing = True` and `_reproduce_partner_id` on the
partner. Remove all direct FSM mutation of the partner's state machine.

**Rationale**: Current code calls `fsm_partner.transition_to("executing")` —
this raises `ValueError` when the partner is in `llm_waiting` or `moving`
(invalid transition). The exception is silently caught by the per-agent
try/except, leaving the originating agent's `_is_reproducing` flag uncleaned.
With flags-only signaling, the partner reacts during its OWN evaluate cycle
next tick. One-tick delay is semantically correct and eliminates the crash.

### D6: Atomic Action Field Management

**Choice**: Create `_reset_action_state(agent)` helper that atomically clears
`current_action`, `current_action_emoji`, `action_duration`,
`action_progress`. Use it in 3 locations: (1) `_fsm_executing` on action
completion, (2) `do_action` director command (which also sets emoji via
`ACTION_EMOJIS`), (3) instinct move path in `_fsm_llm_waiting`.

**Rationale**: Eliminates stale emoji in snapshots (F8) and leaking
`action_duration`/`action_progress` from previous actions (F9). Single source
of truth for action state lifecycle.

## Data Flow

### F1 — Unified LLM Response

```
Tick N:
   Step 2 (FSM): llm_waiting, future not done → instinct action (eat/rest/move)
   Step 4 (Poll): poll_completed() → apply plan → transition to evaluate
Tick N+1:
   Step 2 (FSM): evaluate → find active_plan → execute step 0
```

### F2 — Task Cancellation

```
Director command arrives:
  _execute_director_command()
    → agent.llm_future.cancel()
    → llm.cancel_agent_task(agent_id)
    → _pending_tasks[agent_id].cancel()
    → _resolve() catches CancelledError at await point
    → semaphore released via async with
    → task exits silently, _pending_tasks dict cleaned
```

### F6 — Flags-Only Reproduction

```
Init agent's evaluate:
  → _run_survival_chain → find partner → set flags
  → init agent transitions to executing (reproduce)
  → init agent completes reproduce action
  → offspring created from both parents' stats
  → cleanup resets flags on both agents
Partner's evaluate (next tick):
  → _is_reproducing=True blocks new reproduction attempts
  → normal evaluate logic (no manual FSM transition needed)
```

## File Changes

| File | Action | Fixes | Description |
|------|--------|-------|-------------|
| `backend/app/simulation/engine.py` | Modify | F1,F2,F3,F5,F6,F7,F8,F9 | ~60 lines changed across 8 methods. See detail below. |
| `backend/app/ai/orchestrator.py` | Modify | F2 | Add `_pending_tasks` dict, store task in `_resolve()`, add `cancel_agent_task()`. |
| `backend/app/simulation/agent.py` | Modify | F2 | Add `_pending_tasks` + `cancel_agent_task()` to `MockLLMOrchestrator`. |
| `backend/app/api/ws.py` | No change | — | F4 deferred. |
| `backend/tests/test_dialogue.py` | Modify | F1 | Update 3 tests that call `_fsm_llm_waiting` for result processing → use `_poll_llm_responses`. |
| `backend/tests/test_director_mode.py` | Modify | F2 | Minor: verify task cancellation alongside future cancellation. |

### Engine.py Change Detail

| Method | Lines | Changes |
|--------|-------|---------|
| `_run_agent_fsm` | ~683-712 | F3: Add cooldown guard in `llm_trigger` case before dispatch |
| `_run_survival_chain` | ~1001-1005 | F6: Replace partner FSM mutation with flag setting |
| `_execute_director_command` | ~1078-1081 | F2: Add `self.llm.cancel_agent_task()` after future.cancel(). F5+F7: Full reset logic |
| `_execute_release_all` | new | F5+F7: Extract from `release_all` case, add full agent state reset |
| `_fsm_executing` | ~1456-1459 | F8+F9: Replace inline field clears with `_reset_action_state()` |
| `_fsm_llm_trigger` | ~1480-1485 | F3: Remove cooldown check (moved to `_run_agent_fsm`) |
| `_fsm_llm_waiting` | ~1497-1539 | F1: Remove entire `if agent.llm_future.done()` block (lines 1506-1539) |
| `_poll_llm_responses` | ~1600-1631 | F1: Add `fsm.transition_to("evaluate")` for agents in `llm_waiting` |
| New helper | anywhere | F8+F9: `_reset_action_state(self, agent)` method |

## Interfaces / Contracts

### New Orchestrator Method

Both `RealLLMOrchestrator` and `MockLLMOrchestrator` implement:

```python
def cancel_agent_task(self, agent_id: str) -> None:
    """Cancel the background task for a pending LLM call."""
    task = self._pending_tasks.pop(agent_id, None)
    if task and not task.done():
        task.cancel()
```

### New Engine Helper

```python
def _reset_action_state(self, agent: Agent) -> None:
    """Atomically clear all action-related fields."""
    agent.current_action = None
    agent.current_action_emoji = ""
    agent.action_duration = 0
    agent.action_progress = 0.0
```

### Agent Fields Used (no changes to Agent dataclass)

`_pending_tasks` is orchestrator-local. `_last_llm_tick`, `_is_reproducing`,
`_reproduce_partner_id` already exist on `Agent` via dynamic attributes.

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | F3: Cooldown guard | Set `_last_llm_tick` to `tick-5`, run FSM with agent in `llm_trigger`, verify transition to `evaluate` (not `llm_waiting`) |
| Unit | F5+F7: release_all reset | Set plans, actions, LLM futures on 2 agents, call `release_all`, verify ALL state fields cleared on both |
| Unit | F6: No cross-agent mutation | Initiate reproduction, verify partner FSM state unchanged, partner flags set |
| Unit | F8+F9: Action field atomicity | Complete action, verify all 4 fields cleared. Execute `do_action`, verify emoji set |
| Integration | F1: Poll-only processing | Complete LLM future, call `_fsm_llm_waiting` → verify NO dialogue processing. Call `_poll_llm_responses` → verify dialogue AND transition |
| Integration | F2: Task cancellation | Create `call_async`, cancel via `cancel_agent_task`, verify `_pending_tasks` cleaned, task `.done()` = True |
| Existing | Regression | All director mode tests (20+) should pass. 3 dialogue tests updated for F1 |

### Test Changes Required

1. `test_dialogue.py:test_fsm_llm_waiting_triggers_dialogue` — replace
   `engine._fsm_llm_waiting(...)` with `engine._poll_llm_responses(tick=2)`
2. `test_dialogue.py:test_agent_responds_when_spoken_to` — same pattern
3. `test_dialogue.py:test_dialogue_queue_consumed_after_llm` — same pattern
4. `test_director_mode.py:test_llm_future_cancelled_for_*` — add assertion that
   orchestrator's `_pending_tasks` is also cleaned

## Migration / Rollout

No data migration required. Each fix is independently revertible via git
revert. Execution order ensures F2 (orchestrator API) is available before
engine changes depend on it.

**Rollback**: `git revert <commit>` for each fix in reverse order
(F8+F9 → F6 → F5+F7 → F3 → F1 → F2).

## Open Questions

None. All 8 fixes have clearly specified approaches with detailed code
examples validated against the current codebase.
