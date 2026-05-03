# Tasks: Agent Director Mode

**Test count target**: +25 new tests across all phases (actual: +46 new tests)
**Files to create**: 1 new test module
**Files to modify**: 8 existing files (actual: 9 modified, 1 created)

## Phase 1 — Infrastructure (3 tasks)

### 1.1 [Agent model] Add `injected_thoughts` field — ✅ DONE
- **File**: `backend/app/simulation/agent.py`
- **Description**: Add `injected_thoughts: list[str] = field(default_factory=list)` to the `@dataclass Agent` class. This stores thoughts injected by the user before they're consumed by the LLM pipeline.
- **Depends on**: None
- **Test**: Verify `Agent()` has `injected_thoughts == []` by default. Verify appending to it and clearing works.
- **Acceptance**: Agent dataclass has the new field, all existing tests pass, no existing behavior changes.

### 1.2 [Schema] Add `ClientCommand` Pydantic model — ✅ DONE
- **File**: `backend/app/models/schemas.py`
- **Description**: Add `ClientCommand(BaseModel)` with fields: `type: Literal["move_to", "do_action", "set_plan", "inject_thought", "release", "release_all"]`, `agent_id: str`, `payload: dict`. This validates incoming WebSocket command payloads before they reach the engine.
- **Depends on**: None
- **Test**: Verify valid command types pass validation. Verify invalid types raise `ValidationError`. Verify all 6 command types are accepted.
- **Acceptance**: Pydantic model exists with strict type validation, all 6 command types recognized.

### 1.3 [Schema] Add director mode fields to snapshot schemas — ✅ DONE
- **File**: `backend/app/models/schemas.py`
- **Description**: Add `director_mode: bool = False` to `WorldSnapshot` schema. Optionally add `is_commanded: bool = False` to `AgentState` schema (so frontend knows which agents are actively commanded).
- **Depends on**: 1.2
- **Test**: Verify `WorldSnapshot()` has `director_mode == False` by default. Verify serialization includes both fields.
- **Acceptance**: Snapshot payloads include `director_mode` at root and `is_commanded` per-agent.

## Phase 2 — Backend Implementation (7 tasks)

### 2.1 [Engine] Add `director_mode` flag and `command_queue` dict — ✅ DONE
- **File**: `backend/app/simulation/engine.py`
- **Description**: Add two attributes to `SimulationEngine.__init__()`: `director_mode: bool = False` (engine-level flag) and `command_queue: dict[str, dict] = field(default_factory=dict)` (maps `agent_id` → command payload). When `director_mode` is `False`, the command queue is never checked — zero performance impact.
- **Depends on**: None
- **Test**: Verify `SimulationEngine()` has `director_mode == False` and `command_queue == {}`. Verify setting `director_mode = True` works.
- **Acceptance**: Engine has both new attributes with correct defaults, existing tests pass.

### 2.2 [Engine] Implement `_execute_director_command()` with all 6 command types — ✅ DONE
- **File**: `backend/app/simulation/engine.py`
- **Description**: Add method `_execute_director_command(self, agent: Agent, cmd: dict) -> None` that dispatches by `cmd["type"]`:
  - `move_to`: Validate `x, y` in payload, call `world.find_path()`, set `agent.target_position`, `agent.move_path`, `agent.move_progress = 0.0`, transition FSM to `moving`.
  - `do_action`: Validate `action_id` in payload, set `agent.current_action`, compute `agent.action_duration` via `get_action_duration()`, reset `agent.action_progress = 0.0`, transition FSM to `executing`.
  - `set_plan`: Validate `plan` dict in payload, set `agent.active_plan`, reset `agent.plan_step_index = 0`. Do NOT transition (plan execution is handled by existing FSM on next evaluate).
  - `inject_thought`: Validate `text` in payload, append to `agent.injected_thoughts`, set `agent.last_thought`, reset LLM cooldown timer, force `llm_trigger` state. Do NOT cancel pending LLM future.
  - `release`: Pop agent from `self.command_queue` (no further effect).
  - `release_all`: Clear `self.command_queue`, set `self.director_mode = False`.
- **Depends on**: 2.1
- **Test**: Parametrized pytest — mock agent + engine, verify each command type produces correct side effects on agent state and FSM.
- **Acceptance**: All 6 command types dispatched correctly. `inject_thought` forces `llm_trigger`. `release` removes queue entry. `release_all` clears queue + sets `director_mode = False`.

### 2.3 [Engine] Modify `_fsm_evaluate()` to check queue at START — ✅ DONE
- **File**: `backend/app/simulation/engine.py`
- **Description**: Insert at the VERY START of `_fsm_evaluate()` (line 1061 before any existing logic):
  ```python
  if self.director_mode and agent.id in self.command_queue:
      cmd = self.command_queue.pop(agent.id)
      if cmd["type"] != "inject_thought" and agent.llm_call_pending and agent.llm_future:
          agent.llm_future.cancel()
          agent.llm_call_pending = False
      self._execute_director_command(agent, cmd)
      return  # Skip normal FSM this tick
  ```
  This is the **core interception point**. The early return means the agent's normal FSM is entirely skipped for this tick.
- **Depends on**: 2.1, 2.2
- **Test**: Verify early return when queue has entry. Verify normal FSM runs when queue empty. Verify normal FSM runs when `director_mode = False` (even with queue entries — edge case).
- **Acceptance**: Queued commands are popped and executed at the start of `_fsm_evaluate()`, normal FSM resumes when no command. Zero behavioral change when `director_mode = False`.

### 2.4 [Engine] Add LLM future cancellation for non-thought commands — ✅ DONE
- **File**: `backend/app/simulation/engine.py`
- **Description**: In `_execute_director_command()`, before executing any command except `inject_thought`, check if `agent.llm_call_pending` and `agent.llm_future` are set. If so, call `agent.llm_future.cancel()` and set `agent.llm_call_pending = False`. This ensures user commands take priority over autonomously-generated LLM plans. For `inject_thought`, the pending LLM future is left intact — the thought waits for the next LLM cycle.
- **Depends on**: 2.2
- **Test**: Mock `asyncio.Future`, verify `.cancel()` is called for `move_to`/`do_action`/`set_plan`. Verify `.cancel()` is NOT called for `inject_thought`.
- **Acceptance**: Non-thought commands cancel pending LLM futures. `inject_thought` does NOT cancel.

### 2.5 [WebSocket] Implement `command_dispatcher()` and wire into receive loop — ✅ DONE
- **File**: `backend/app/api/ws.py`
- **Description**: Replace the `websocket.receive_json()` placeholder. Create `command_dispatcher(msg: dict, engine: SimulationEngine) -> None` function:
  - Expects `msg["type"] == "command"`
  - Extracts `command_type`, `agent_id`, `payload` from `msg["payload"]`
  - Validates `command_type` ∈ allowed set (log WARNING on unknown)
  - Validates `agent_id` exists in engine (log WARNING if not)
  - Enqueues to `engine.command_queue[agent_id] = msg["payload"]`
  - If `command_type == "release_all"`, also sets `engine.director_mode = False`
  - Non-blocking: synchronous, no `await`
  
  Wire into `websocket_endpoint()`: receive the JSON, if `data.get("type") == "command"`, call `command_dispatcher(data, engine)`, else continue to existing handling.
- **Depends on**: 2.1
- **Test**: Unit test `command_dispatcher()` with mock engine — verify queue state after dispatch. Unit test with invalid command type (WARNING logged, no crash). All existing WS tests pass.
- **Acceptance**: Incoming `type: "command"` messages are dispatched to engine's command queue. Unknown types are logged and ignored. Existing WS message types are unaffected.

### 2.6 [LLM Orchestrator] Modify `build_prompt()` for thought injection — ✅ DONE
- **Files**: `backend/app/ai/orchestrator.py` (RealLLMOrchestrator), `backend/app/simulation/agent.py` (MockLLMOrchestrator)
- **Description**: In both `RealLLMOrchestrator.build_prompt()` and `MockLLMOrchestrator.build_prompt()`: after existing prompt construction, prepend each injected thought as `"A voice in your head says: {thought}"` before the core prompt. After prepending, append each thought to `agent.monologue_history`, then clear `agent.injected_thoughts`.
  
  Implementation in RealLLMOrchestrator (after line 157 of `orchestrator.py`, before `return build_agent_prompt(...)`):
  ```python
  for thought in agent.injected_thoughts:
      prompt = f"A voice in your head says: {thought}\n\n{prompt}"
  agent.monologue_history.extend(agent.injected_thoughts)
  agent.injected_thoughts.clear()
  ```
- **Depends on**: 1.1
- **Test**: Call `build_prompt()` on agent with `injected_thoughts=["Go talk to Ena"]`. Verify prompt contains `"A voice in your head says: Go talk to Ena"`. Verify thought is in `monologue_history` after. Verify `injected_thoughts` is empty after.
- **Acceptance**: Injected thoughts appear in LLM prompts as "A voice in your head says: ...", are appended to monologue history, and cleared from injection buffer.

### 2.7 [Snapshot] Expose director mode state — ✅ DONE
- **File**: `backend/app/simulation/snapshot.py`
- **Description**: Modify `WorldSnapshotBuilder` to accept and expose director mode state. Options:
  - A: Pass `engine` or `command_queue` + `director_mode` to `build()` / `build_delta()` as parameters
  - B: Pass during construction (less coupling)
  
  In `_build_agent_state()`, add `is_commanded: bool = agent.id in engine.command_queue`. In `build()`/`build_delta()`, add `director_mode` to the `WorldSnapshot`.
  
  **Note**: The snapshot builder currently has no access to the engine. Either pass the engine ref during construction, or pass `director_mode` and `commanded_agent_ids` directly to `build()`/`build_delta()`. The latter is cleaner (no circular dep).
- **Depends on**: 1.3, 2.1
- **Test**: Verify snapshot includes `director_mode` boolean. Verify `is_commanded` is `True` for agents in command queue and `False` otherwise.
- **Acceptance**: Snapshot payloads include director mode state for frontend consumption.

## Phase 3 — Frontend Implementation (8 tasks)

### 3.1 [Store] Add `directorMode` state to uiStore — ✅ DONE
- **File**: `frontend/src/lib/stores/uiStore.svelte.js`
- **Description**: Add `directorMode: false` to the writable store state. Add `setDirectorMode(bool)` method and `toggleDirectorMode()` for convenience. The store is a Svelte writable, so all consumers reactively update.
- **Depends on**: None
- **Test**: Verify default is `false`. Verify `setDirectorMode(true)` updates the value. Verify `toggleDirectorMode()` flips it.
- **Acceptance**: `uiStore.directorMode` available and reactive, default `false`.

### 3.2 [HUD] Add Director Mode toggle button — ✅ DONE
- **File**: `frontend/src/lib/components/HUD.svelte`
- **Description**: Add a button after the Pause/Resume button showing `"Director: OFF"` (gray) / `"Director: ON"` (gold). On click:
  - If currently OFF: set `uiStore.directorMode = true`
  - If currently ON: send `release_all` command via `ws.send()`, then set `uiStore.directorMode = false`
  
  Style: gold background (#FFD700) when ON, gray when OFF. Add a visual indicator (e.g., small crown emoji 👑 or similar).
  
  Import `send` from `$lib/components/ws.js`.
- **Depends on**: 3.1
- **Test**: Manual — toggle button appears in HUD, sends correct WS messages, changes color.
- **Acceptance**: Toggle button visible in HUD, sends `release_all` when turning OFF, sets state when turning ON.

### 3.3 [AgentInspector] Add command panel with action buttons — ✅ DONE
- **File**: `frontend/src/lib/components/AgentInspector.svelte`
- **Description**: When `uiStore.directorMode === true` AND an agent is selected, show a command panel section with action buttons: Gather 🌾 Chop 🪓 Rest 💤 Build 🔧 Mine ⛏️ Guard 🛡️. Each button sends a `do_action` command via `ws.send()` with the corresponding `action_id`. 
  
  Import `send` from `$lib/components/ws.js`. The command payload format:
  ```json
  {
    "type": "command",
    "payload": {
      "type": "do_action",
      "agent_id": "{selectedAgentId}",
      "payload": { "action_id": "CHOP" }
    }
  }
  ```
- **Depends on**: 3.1
- **Test**: Manual — action buttons visible in director mode, hidden when OFF. Each button sends correct WS command.
- **Acceptance**: Command panel with action buttons appears in AgentInspector when director mode is ON. Each button sends correct `do_action` command.

### 3.4 [AgentInspector] Add thought injection textarea — ✅ DONE
- **File**: `frontend/src/lib/components/AgentInspector.svelte`
- **Description**: Below the action buttons, add a textarea for thought injection + "Inject" button. When the user types text and clicks "Inject" (or presses Ctrl+Enter), send an `inject_thought` command via `ws.send()` with the text content. Clear the textarea after sending. Add a placeholder: "Whisper a thought into the agent's mind..."
  
  Command format:
  ```json
  {
    "type": "command",
    "payload": {
      "type": "inject_thought",
      "agent_id": "{selectedAgentId}",
      "payload": { "text": "{user input}" }
    }
  }
  ```
- **Depends on**: 3.1, 3.3
- **Test**: Manual — textarea visible in director mode with agent selected. Sending injects the thought.
- **Acceptance**: Textarea + Inject button present. Sends `inject_thought` command with user text. Clears after send.

### 3.5 [AgentInspector] Add Release button — ✅ DONE
- **File**: `frontend/src/lib/components/AgentInspector.svelte`
- **Description**: Below the command panel, add a "Release" button that sends a `release` command for the currently selected agent. Also add a status label showing "Commanded" (gold badge) vs "Autonomous" (gray) based on whether the agent has a commanded status. This status comes from the snapshot's `is_commanded` field.
  
  Import `simulationStore` to read `is_commanded` from agent state.
  
  Command format:
  ```json
  {
    "type": "command",
    "payload": {
      "type": "release",
      "agent_id": "{selectedAgentId}",
      "payload": {}
    }
  }
  ```
- **Depends on**: 3.1, 3.3
- **Test**: Manual — Release button visible in director mode. "Commanded"/"Autonomous" label updates based on agent state.
- **Acceptance**: Release button present. Status label shows commanded state. Sends `release` command on click.

### 3.6 [Canvas2D] Add right-click `move_to` handler — ✅ DONE
- **File**: `frontend/src/lib/canvas2d/Canvas2D.svelte`
- **Description**: Add a contextmenu (right-click) event listener on the canvas wrapper div. When `uiStore.directorMode === true` AND `uiStore.selectedAgentId !== null`: prevent default context menu, convert pixel coordinates to grid tile coordinates (using `TILE_SIZE`), and send a `move_to` command via `ws.send()`. 
  
  Import `send` from `$lib/components/ws.js` and `uiStore` from the stores. The pixel-to-tile conversion: `tileX = Math.floor(event.offsetX / TILE_SIZE)`, `tileY = Math.floor(event.offsetY / TILE_SIZE)` — but account for viewport scroll/zoom if applicable.
  
  When director mode is OFF or no agent selected, let the default browser context menu through (camera pan remains untouched).
  
  Command format:
  ```json
  {
    "type": "command",
    "payload": {
      "type": "move_to",
      "agent_id": "{selectedAgentId}",
      "payload": { "x": tileX, "y": tileY }
    }
  }
  ```
- **Depends on**: 3.1
- **Test**: Manual — right-click in director mode + selected agent sends `move_to`. Right-click in normal mode shows context menu.
- **Acceptance**: Right-click with director mode ON + agent selected sends `move_to` command. Right-click with director mode OFF preserves default behavior.

### 3.7 [Canvas2D] Change selection ring color in director mode — ✅ DONE
- **File**: `frontend/src/lib/canvas2d/OverlayLayer.ts`
- **Description**: Modify `OverlayLayer` to accept a `directorMode` parameter. When `directorMode === true`, change `RING_COLOR` from `0x00ff88` (green) to `0xffd700` (gold). The color change should be reactive — update when director mode toggles without recreating the layer.
  
  Options:
  - Pass a `color` parameter to `setTarget()` or add a `setDirectorMode(bool)` method
  - Subscribe to `uiStore` directly within OverlayLayer
  
  Preferred approach: pass it as a parameter. Add `setRingColor(color: number)` method to `OverlayLayer`, and call it from `Canvas2D.svelte` in the `$effect` that watches `$uiStore.directorMode`.
- **Depends on**: 3.1
- **Test**: Manual — ring changes from green to gold when toggling director mode, back to green when toggling off.
- **Acceptance**: Selection ring is gold (#FFD700) in director mode, green (0x00ff88) when OFF.

### 3.8 [AgentSprites] Add badge indicator for commanded agents — ✅ DONE
- **File**: `frontend/src/lib/canvas2d/AgentSprites.ts`
- **Description**: Add a small visual indicator (small crown/badge) on agent sprites whose `agent_id` is in the commanded agents set. The set of commanded agent IDs comes from the snapshot — specifically, agents where `is_commanded === true`.
  
  Implementation options:
  - Draw a small gold Graphics shape on top of the sprite
  - Add a small child sprite/graphic to each commanded agent's sprite
  
  Accept a `commandedAgents: Set<string>` parameter in the `update()` method. For each agent sprite, if the ID is in the set and no badge child exists yet, add a small gold triangle/circle. If the ID is NOT in the set and a badge exists, remove it.
- **Depends on**: 3.1, 2.7 (for `is_commanded` in snapshot)
- **Test**: Manual — commanded agents show a badge, non-commanded agents don't. Badge disappears when agent is released.
- **Acceptance**: Commanded agents display a visual indicator (gold badge/crown). Non-commanded agents have no badge.

## Phase 4 — Testing (5 tasks)

### 4.1 [Backend Tests] Command queue and FSM interception — ✅ DONE
- **File**: `backend/tests/test_director_mode.py` (new)
- **Description**: Tests for:
  - Command queue check at START of `_fsm_evaluate()` causes early return
  - Normal FSM runs when queue is empty
  - Normal FSM runs when `director_mode = False` (even with stale queue entries)
  - `release` removes single agent's entry from command queue
  - `release_all` clears entire queue AND sets `director_mode = False`
  - One agent's command does not affect another agent's FSM
- **Depends on**: 2.1, 2.2, 2.3
- **Test**: Parametrized pytest with mock engine and agents.
- **Acceptance**: All command queue interception tests pass. Non-interference confirmed.

### 4.2 [Backend Tests] Command type dispatch and LLM cancellation — ✅ DONE
- **File**: `backend/tests/test_director_mode.py`
- **Description**: Tests for `_execute_director_command()`:
  - `move_to` sets `target_position` and transitions to `moving`
  - `do_action` sets `current_action` and transitions to `executing`
  - `set_plan` sets `active_plan` and resets `plan_step_index`
  - `inject_thought` appends to `injected_thoughts`, forces `llm_trigger`
  - `release` removes from queue (no FSM transition)
  - `release_all` clears queue + sets `director_mode = False`
  - LLM future cancellation: verify `.cancel()` called for `move_to`/`do_action`/`set_plan`
  - LLM future NOT cancelled for `inject_thought`
- **Depends on**: 2.2, 2.4
- **Test**: Parametrized pytest with mock agent + engine + `asyncio.Future`.
- **Acceptance**: All 6 command types produce correct side effects. LLM cancellation correct per type.

### 4.3 [Backend Tests] Thought injection pipeline — ✅ DONE
- **File**: `backend/tests/test_director_mode.py`
- **Description**: Tests for:
  - `injected_thoughts` list defaults to empty on new Agent
  - `build_prompt()` includes `"A voice in your head says: {thought}"` for each injected thought
  - Multiple injected thoughts each appear in the prompt
  - `monologue_history` contains the thought after `build_prompt()` call
  - `injected_thoughts` is cleared after `build_prompt()` call
  - Works for both `MockLLMOrchestrator` and `RealLLMOrchestrator`
- **Depends on**: 1.1, 2.6
- **Test**: Direct calls to `build_prompt()` with various injected thought states.
- **Acceptance**: All thought injection pipeline tests pass.

### 4.4 [Backend Tests] FSM non-interference when director mode OFF — ✅ DONE
- **File**: `backend/tests/test_director_mode.py`
- **Description**: Verify that:
  - Setting `director_mode = False` (default) produces identical agent behavior to pre-director-mode engine
  - The command queue is never checked when `director_mode = False` (zero overhead)
  - Existing FSM tests from `test_engine.py` still pass with the new engine changes
  - Agent can still use LLM, move, execute actions, etc. normally
- **Depends on**: 2.1, 2.2, 2.3
- **Test**: Run existing FSM tests alongside new ones. Verify the director mode changes don't alter normal behavior.
- **Acceptance**: All existing engine tests pass unchanged. Director mode state has zero impact when OFF.

### 4.5 [Backend Tests] WebSocket command dispatcher integration — ✅ DONE
- **File**: `backend/tests/test_director_mode.py`
- **Description**: Integration tests for `command_dispatcher()` in `ws.py`:
  - Valid command message correctly enqueues in `engine.command_queue`
  - Invalid command type logs WARNING (use `caplog`) and does not crash
  - `release_all` command sets `engine.director_mode = False`
  - Non-command message types pass through unchanged
  - Unknown agent_id logs WARNING but does not crash
  - Dispatch is synchronous and non-blocking
- **Depends on**: 2.5
- **Test**: Using mock engine, call `command_dispatcher()` directly with various messages.
- **Acceptance**: All dispatcher integration tests pass. Messages dispatched correctly. Edge cases handled gracefully.
