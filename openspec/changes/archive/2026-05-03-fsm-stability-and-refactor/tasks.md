# Tasks: FSM Stability and Refactor

**Status: ✅ COMPLETE — All 15 tasks implemented and verified (563 tests pass)**

## Execution Order

Infrastructure (F2 orchestrator API) → P0 Fixes (F1, F2 engine) → P1 Fixes (F3, F5+F7, F6, F8+F9) → Testing

Each fix is independently revertible. Phase 1 MUST complete before Phases 2-3.

---

## Phase 1: Infrastructure ✅

### ✅ 1.1 Track background task in `RealLLMOrchestrator` + add `cancel_agent_task`

**File**: `backend/app/ai/orchestrator.py`

**Changes**:
1. Add `self._pending_tasks: dict[str, asyncio.Task] = {}` to `RealLLMOrchestrator.__init__` (around line 49)
2. In `call_async` (line 249), store the task: `self._pending_tasks[agent_id] = task` before the callback line
3. Add method:
   ```python
   def cancel_agent_task(self, agent_id: str) -> None:
       task = self._pending_tasks.pop(agent_id, None)
       if task and not task.done():
           task.cancel()
   ```
4. In `poll_completed`, clean up `_pending_tasks` when an entry is removed from `_pending`

**Verify**: Unit test — create a `call_async`, call `cancel_agent_task`, verify `_pending_tasks` dict is cleaned, task is `.done()`.

**Effort**: ~15 min

---

### 1.2 Track background task in `MockLLMOrchestrator` + add `cancel_agent_task`

**File**: `backend/app/simulation/agent.py` (MockLLMOrchestrator lives here)

**Changes**:
1. Add `self._pending_tasks: dict[str, asyncio.Task] = {}` to `MockLLMOrchestrator.__init__` (line 245)
2. In `call_async` (line 563), capture the task: `task = asyncio.create_task(_resolve())` then `self._pending_tasks[agent_id] = task`
3. Add same `cancel_agent_task(self, agent_id)` method
4. In `poll_completed`, clean up `_pending_tasks` when removing from `_pending`

**Verify**: Unit test — create a `call_async`, cancel, verify state cleanup.

**Effort**: ~10 min

---

## Phase 2: Implementation — P0 Fixes

### 2.1 F2: Cancel background task in `_execute_director_command`

**File**: `backend/app/simulation/engine.py`

**Changes**:
- In `_execute_director_command` (line 1078-1081), after `agent.llm_future.cancel()` and `agent.llm_call_pending = False`, add:
  ```python
  self.llm.cancel_agent_task(agent.id)
  ```

**Note**: This depends on infrastructure (Phase 1) — `cancel_agent_task` must exist on both orchestrators first.

**Verify**: Existing tests `test_llm_future_cancelled_for_*` (4 tests) still pass. Add assertion that `_pending_tasks` is also cleaned.

**Effort**: ~5 min (one line change)

---

### 2.2 F1: Remove result processing from `_fsm_llm_waiting`

**File**: `backend/app/simulation/engine.py`

**Changes**:
- In `_fsm_llm_waiting` (lines 1506-1539), remove the entire `if agent.llm_future.done():` block (including the try/except, result processing, dialogue queue cleanup, and the `fsm.transition_to("evaluate")` at the end)
- Keep the `else` branch (instinct actions: waiting, poison, eat, rest, move) — that's the instinct-only behavior

**What remains after removal**:
- The `if not agent.llm_future:` guard (lines 1500-1504) → transition to evaluate
- The `else:` branch (lines 1540-1594) → instinct actions only

**Verify**: Agent in `llm_waiting` with a completed future acts on instinct (does NOT process LLM result). Poll path is now the sole handler.

**Effort**: ~10 min

---

### 2.3 F1: Update `_poll_llm_responses` to be sole handler (add state transition)

**File**: `backend/app/simulation/engine.py`

**Changes**:
- In `_poll_llm_responses` (lines 1600-1631), after setting the plan and cleaning up (line 1627), add state transition:
  ```python
  fsm = self.fsms[agent_id]
  if fsm.current_state == "llm_waiting":
      fsm.transition_to("evaluate")
  ```

**Why**: Previously, `_fsm_llm_waiting` handled the transition. Now that it's removed, `_poll_llm_responses` must transition the agent from `llm_waiting` to `evaluate` when a plan is set. For agents NOT in `llm_waiting` (director interrupted), the plan is set WITHOUT a transition.

**Verify**: Test that after poll processing, an agent in `llm_waiting` transitions to `evaluate`. Test that an agent in `executing`/`moving` gets the plan set but does NOT transition.

**Effort**: ~10 min

---

## Phase 3: Implementation — P1 Fixes

### 3.1 F3: Add cooldown guard in `_run_agent_fsm` dispatch

**File**: `backend/app/simulation/engine.py`

**Changes**:
1. In `_run_agent_fsm` (line 706-707), change the `llm_trigger` case:
   ```python
   case "llm_trigger":
       last = getattr(agent, '_last_llm_tick', -999)
       if last > 0 and tick - last < 30:
           fsm.transition_to("evaluate")  # skip LLM, run survival chain
       else:
           self._fsm_llm_trigger(agent, fsm, tick)
   ```
2. In `_fsm_llm_trigger` (lines 1480-1485), REMOVE the cooldown check block (the `if last > 0 and tick - last < 30:` block that transitions to `llm_waiting`)

**What the cooldown guard prevents**: Agent entering `llm_trigger` → transitioning to `llm_waiting` with no future → returning to `evaluate` → re-entering `llm_trigger` next tick (the ping-pong loop). The guard at dispatch level short-circuits directly to `evaluate`, skipping `llm_trigger` entirely.

**Verify**: Set `_last_llm_tick = tick-5`, agent in `llm_trigger`, tick difference < 30 → transitions to `evaluate` (not `llm_waiting`). After cooldown expires, normal LLM trigger fires.

**Effort**: ~10 min

---

### 3.2 F5+F7: Complete state reset in `release_all` + `release` commands

**File**: `backend/app/simulation/engine.py`

**Changes**:

**For `release_all`** (replace lines 1135-1137):
```python
elif cmd_type == "release_all":
    self.command_queue.clear()
    self.director_mode = False
    for a in self.agents:
        # Cancel pending LLM
        if a.llm_call_pending and a.llm_future:
            a.llm_future.cancel()
            self.llm.cancel_agent_task(a.id)
        # Clear all director-imposed state
        a.active_plan = None
        a.plan_step_index = 0
        a.current_action = None
        a.current_action_emoji = ""
        a.action_duration = 0
        a.action_progress = 0.0
        a.target_position = None
        a.move_path = None
        a.move_progress = 0.0
        a.injected_thoughts = []
        a._last_llm_tick = -999
        a.llm_call_pending = False
        a.llm_future = None
```

**For `release`** (replace lines 1131-1133):
```python
elif cmd_type == "release":
    # Full reset for single agent (same fields as release_all)
    if agent.llm_call_pending and agent.llm_future:
        agent.llm_future.cancel()
        self.llm.cancel_agent_task(agent.id)
    agent.active_plan = None
    agent.plan_step_index = 0
    agent.current_action = None
    agent.current_action_emoji = ""
    agent.action_duration = 0
    agent.action_progress = 0.0
    agent.target_position = None
    agent.move_path = None
    agent.move_progress = 0.0
    agent.injected_thoughts = []
    agent._last_llm_tick = -999
    agent.llm_call_pending = False
    agent.llm_future = None
    fsm.transition_to("evaluate")
```

**Design note**: The `release_all` iteration over `self.agents` implicitly calls `cancel_agent_task` for each agent — this requires Phase 1 infrastructure.

**Verify**: Set plans, actions, LLM futures on 2 agents, call `release_all` → ALL state fields cleared on both, director_mode=False. Single-agent `release` → fields cleared, agent transitions to `evaluate`.

**Effort**: ~15 min

---

### 3.3 F6: Flags-only reproduction signaling — remove partner FSM mutation

**File**: `backend/app/simulation/engine.py`

**Changes**:
- In `_run_survival_chain` (lines 1001-1005), replace the partner FSM mutation block:
  ```python
  # OLD:
  fsm_partner = self.fsms[partner.id]
  if fsm_partner.current_state == "idle":
      fsm_partner.transition_to("evaluate")
  if fsm_partner.current_state != "executing":
      fsm_partner.transition_to("executing")
  
  # NEW: Remove entirely — just keep the flag setting above (lines 998-999)
  ```
- Ensure partner's cleanup in `_fsm_executing` (lines 1450-1454) already resets `_is_reproducing` and `_reproduce_partner_id` for both agents — this should already work.

**What's preserved**: Lines 990-999 (setting both agents' actions, durations, progress, partner IDs, and the originating agent's transition to `executing`). Lines 1001-1005 are simply deleted.

**Why safe**: The partner will naturally detect reproduction flags during its own `evaluate` cycle next tick. The one-tick delay is semantically correct.

**Verify**: Initiate reproduction, verify partner FSM state is unchanged (stays in whatever state it was in), partner's `_is_reproducing` flag is set. No `ValueError` from invalid transitions.

**Effort**: ~5 min

---

### 3.4 F8+F9: Create `_reset_action_state` helper + apply in 3 locations

**File**: `backend/app/simulation/engine.py`

**Changes**:

**New helper method** (add anywhere in engine.py, e.g., near line 1070):
```python
def _reset_action_state(self, agent: Agent) -> None:
    """Atomically clear all action-related fields."""
    agent.current_action = None
    agent.current_action_emoji = ""
    agent.action_duration = 0
    agent.action_progress = 0.0
```

**Location 1 — `_fsm_executing` action completion (lines 1457-1459)**:
Replace:
```python
agent.action_progress = 0.0
agent.action_duration = 0
agent.current_action = None
```
With:
```python
self._reset_action_state(agent)
```

**Location 2 — `do_action` director command (line 1102)**:
After `agent.current_action = action_id`, add emoji setting:
```python
from app.simulation.actions import ACTION_EMOJIS  # already imported at top
agent.current_action_emoji = ACTION_EMOJIS.get(action_id, "")
```

**Location 3 — Instinct move path in `_fsm_llm_waiting` (lines 1580-1594)**:
Before setting `agent.current_action = "seeking water"/"seeking food"`, add:
```python
self._reset_action_state(agent)
```

**Verify**: Complete action in `_fsm_executing` → all 4 fields cleared. `do_action` → emoji set via `ACTION_EMOJIS`. Instinct move → stale duration/progress cleared.

**Effort**: ~15 min

---

## Phase 4: Testing

### 4.1 Update existing dialogue tests for F1

**File**: `backend/tests/test_dialogue.py`

**Changes**:
Update 3 tests that call `_fsm_llm_waiting` for LLM result processing:

1. `test_fsm_llm_waiting_triggers_dialogue` (line 261): Replace `engine._fsm_llm_waiting(a1, fsm, tick=2)` with `engine._poll_llm_responses(tick=2)`. Assert that `_fsm_llm_waiting` does NOT process dialogue.

2. `test_agent_responds_when_spoken_to` (line 279): Replace `engine._fsm_llm_waiting(a2, ..., tick=2)` with `engine._poll_llm_responses(tick=2)`.

3. `test_dialogue_queue_consumed_after_llm` (line 328): Replace `engine._fsm_llm_waiting(a1, fsm, tick=2)` with `engine._poll_llm_responses(tick=2)`.

For each test, verify the agent is in `llm_waiting` before calling poll, so the transition to `evaluate` occurs.

**Effort**: ~15 min

---

### 4.2 New tests for F1 unified poll path

**File**: `backend/tests/test_dialogue.py` (or new `backend/tests/test_fsm_stability.py`)

**Scenarios**:

1. **Response arrives for agent in `llm_waiting`**:
   - Agent in `llm_waiting`, future completes → call `_poll_llm_responses`
   - Assert: plan set, `llm_call_pending` is False, FSM is in `evaluate`
   - Call `_fsm_llm_waiting` → assert: instinct action only, NO plan processing

2. **Response arrives for agent NOT in `llm_waiting`** (director interrupted):
   - Agent in `executing`, `llm_future` completes → call `_poll_llm_responses`
   - Assert: `active_plan` set, but FSM state is STILL `executing` (no transition)

3. **`_fsm_llm_waiting` with completed future does NOT process result**:
   - Set up agent in `llm_waiting` with completed future
   - Call `_fsm_llm_waiting` → assert: `active_plan` is unchanged, agent acts on instinct

**Effort**: ~20 min

---

### 4.3 Update existing director mode tests for F2

**File**: `backend/tests/test_director_mode.py`

**Changes**:
In the 4 tests `test_llm_future_cancelled_for_*` (lines 269, 292, 314, 337), add assertions:
- Verify `engine.llm._pending_tasks` does not contain the agent_id after cancellation
- (The `future.cancelled()` and `agent.llm_call_pending` assertions remain)

Note: Since these tests create futures via `loop.create_future()` directly (not via `call_async`), the `_pending_tasks` dict won't have entries. Either:
- (a) Refactor tests to use `llm.call_async()` which creates the task, OR
- (b) Add a separate test that specifically verifies task cancellation via `call_async`

Option (b) is cleaner — leaves existing tests intact and adds new integration-level test.

**New test**: Create engine, call `llm.call_async(agent_id, prompt)`, verify `_pending_tasks` has entry, cancel via `_execute_director_command`, verify `_pending_tasks` cleaned.

**Effort**: ~15 min

---

### 4.4 New tests for F5+F7 complete release/reset

**File**: `backend/tests/test_director_mode.py`

**Scenarios**:

1. **`release_all` full reset**:
   - Create 2 agents with active plans, actions, LLM futures, injected thoughts, positions, paths
   - Enable director_mode with commands queued
   - Call `_execute_director_command` with `release_all`
   - Assert for ALL agents: `active_plan=None`, `plan_step_index=0`, `current_action=None`, `current_action_emoji=""`, `action_duration=0`, `action_progress=0.0`, `target_position=None`, `move_path=None`, `injected_thoughts=[]`, `_last_llm_tick=-999`, `llm_call_pending=False`, `llm_future=None`
   - Assert: `director_mode=False`, `command_queue` empty

2. **Single `release` full reset**:
   - One agent with plan, action, thought, LLM future
   - Call release
   - Assert: same fields cleared for that agent
   - Assert: FSM is in `evaluate`

**Effort**: ~20 min

---

### 4.5 New tests for F6 natural reproduction (no cross-agent mutation)

**File**: `backend/tests/test_engine.py` (reproduction tests likely there) or new `backend/tests/test_fsm_stability.py`

**Scenarios**:

1. **Partner FSM unchanged during reproduction**:
   - Set up two agents with compatible stats, positions within radius
   - Set partner FSM to `llm_waiting` (a state where `transition_to("executing")` would fail)
   - Run `_run_survival_chain` through evaluate → reproduction triggers
   - Assert: partner FSM state is STILL `llm_waiting` (NOT changed to `executing`)
   - Assert: partner's `_is_reproducing` and `_reproduce_partner_id` are set
   - Assert: originating agent transitions to `executing` with reproduce action

2. **Partner reacts on next evaluate**:
   - After reproduction init, run partner's FSM next tick
   - Assert: partner sees `_is_reproducing` flag and handles appropriately

**Effort**: ~20 min

---

### 4.6 New tests for F3, F8+F9

**File**: `backend/tests/test_fsm_stability.py` (new dedicated file, or add to existing)

**F3 — Cooldown guard**:

1. **Cooldown active → skip to evaluate**:
   - Agent in `llm_trigger`, `_last_llm_tick = tick-5` (5 < 30 cooldown)
   - Call `_run_agent_fsm` → assert: FSM transitions to `evaluate`
   - Assert: `_fsm_llm_trigger` is NOT called (no future created)

2. **Cooldown expired → normal LLM trigger**:
   - Agent in `llm_trigger`, `_last_llm_tick = tick-40` (40 >= 30, expired)
   - Call `_run_agent_fsm` → assert: FSM transitions to `llm_waiting`
   - Assert: `llm_future` is set

**F8+F9 — Action field atomicity**:

1. **Action completion clears all fields**:
   - Agent has `current_action="chop"`, `current_action_emoji="🪓"`, `action_duration=5`, `action_progress=0.5`
   - Call `_reset_action_state(agent)` (or run through `_fsm_executing` completion)
   - Assert: all 4 fields are None/0/""

2. **`do_action` sets emoji via ACTION_EMOJIS**:
   - Issue `do_action` with `action_id = "chop"`
   - Assert: `current_action_emoji == "🪓"` (from ACTION_EMOJIS mapping)

3. **No stale fields after instinct move**:
   - Agent had previous action with `action_duration=5`, `action_progress=0.8`
   - Instinct move path executes → assert: `action_duration=0`, `action_progress=0.0`

**Effort**: ~25 min

---

## Summary ✅

| ID | Fix | Phase | Files | Status |
|----|-----|-------|-------|--------|
| 1.1 | F2: RealLLMOrchestrator task tracking | Infrastructure | orchestrator.py | ✅ |
| 1.2 | F2: MockLLMOrchestrator task tracking | Infrastructure | agent.py | ✅ |
| 2.1 | F2: Cancel task in _execute_director_command | P0 | engine.py | ✅ |
| 2.2 | F1: Remove result processing from _fsm_llm_waiting | P0 | engine.py | ✅ |
| 2.3 | F1: Add transition to _poll_llm_responses | P0 | engine.py | ✅ |
| 3.1 | F3: Cooldown guard in _run_agent_fsm | P1 | engine.py | ✅ |
| 3.2 | F5+F7: Complete release/release_all reset | P1 | engine.py | ✅ |
| 3.3 | F6: Flags-only reproduction signaling | P1 | engine.py | ✅ |
| 3.4 | F8+F9: _reset_action_state helper + 3 locations | P1 | engine.py | ✅ |
| 4.1 | Update 3 dialogue tests | Testing | test_dialogue.py | ✅ |
| 4.2 | New tests for F1 poll path | Testing | test_dialogue.py | ✅ |
| 4.3 | Update director mode tests for F2 | Testing | test_director_mode.py | ✅ |
| 4.4 | New tests for F5+F7 release/reset | Testing | test_director_mode.py | ✅ |
| 4.5 | New tests for F6 reproduction | Testing | test_engine.py | ✅ |
| 4.6 | New tests for F3, F8+F9 | Testing | test_engine.py | ✅ |
| | **Total** | | **563 tests passing** | **15/15 ✅** |

## Execution Constraints

| Constraint | Details |
|------------|---------|
| Phase 1 must complete before Phase 2 begins | F2 engine changes depend on orchestrator API |
| Phase 2 must complete before Phase 4.1-4.3 | Those tests verify F1+F2 behavior |
| Phase 3 is independent of Phase 2 ordering | 3.1-3.4 can be done in any order |
| Phase 4.4-4.6 must wait for Phase 3 completion | Tests verify specific P1 fixes |
| New test file | Consider creating `backend/tests/test_fsm_stability.py` for dedicated new tests |
