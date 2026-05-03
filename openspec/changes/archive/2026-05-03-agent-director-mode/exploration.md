## Exploration: Agent Director Mode

### Current State

**Backend — Agent Autonomy Flow:**
- Agents are fully autonomous via a 6-state FSM: `idle → evaluate → moving / executing / llm_trigger → llm_waiting`
- The `_fsm_evaluate()` method (engine.py:1061) runs a priority chain: feed child → role priorities → survival chain → LLM plan execution → LLM trigger
- Agents get plans from LLM (RealLLMOrchestrator or MockLLMOrchestrator fallback). Plans are dicts with `steps` (list of action dicts), `reasoning`, `intention`, etc.
- There is NO mechanism to override or intercept agent decisions. The FSM runs purely on internal state.

**Backend — WebSocket:**
- `backend/app/api/ws.py`: Receives JSON from clients via `receive_json()`, but the received data is **discarded** — there's a `# Command processing placeholder` comment
- `ClientMessage` schema (schemas.py:77-79) defines `type` as `"command" | "config_change" | "agent_edit"`, but none are actually processed
- `ConnectionManager.broadcast()` sends snapshots to all connected clients

**Backend — Agent Override Points (key discovery):**
- **Plan override**: `agent.active_plan` (dict with `steps`) and `agent.plan_step_index` — if set, the FSM skips the survival chain and LLM trigger, going directly to plan execution
- **Direct action**: `agent.current_action`, `agent.action_progress`, `agent.action_duration` — can be set to bypass the normal FSM
- **Movement**: `agent.target_position` and `agent.move_path` — can be set for direct movement control
- **Thought injection**: `agent.last_thought`, `agent.monologue_history`, `agent.system_prompt` — all directly settable and serialized to frontend
- **LLM pipeline**: `agent.llm_call_pending` and `agent.llm_future` — setting these skips LLM waits and cooldowns

**Frontend — Selection Already Works:**
- Click on agent sprite → `uiStore.selectAgent(id)` → shows `AgentInspector` overlay
- `OverlayLayer` shows pulsing green ring on selected agent (followed via Ticker)
- `ws.js` has `send(data)` function already wired — can send JSON to backend
- `uiStore.selectedAgentId` is available everywhere

**Frontend — Missing:**
- No "command panel" in AgentInspector or HUD to send commands
- No right-click handler for click-to-move
- No director-mode toggle
- No command input field for thought injection

### Affected Areas

- `backend/app/api/ws.py` — Command processing placeholder → full command dispatcher
- `backend/app/simulation/engine.py` — Add director mode flag, command queue, FSM interception logic
- `backend/app/simulation/agent.py` — Add `commanded` flag or similar director-mode marker
- `backend/app/models/schemas.py` — Add command message schemas (move_to, set_action, inject_thought, toggle_director)
- `backend/app/simulation/snapshot.py` — Possibly expose director mode state in snapshots
- `backend/app/main.py` — Possibly wire director mode to engine lifecycle
- `frontend/src/lib/stores/uiStore.svelte.js` — Add `directorMode`, `commandTarget`, pending command state
- `frontend/src/lib/components/AgentInspector.svelte` — Add command panel (action buttons, thought input, move-to-click)
- `frontend/src/lib/components/HUD.svelte` — Add director mode toggle button
- `frontend/src/lib/canvas2d/OverlayLayer.ts` — Change selection ring visual when in director mode
- `frontend/src/lib/canvas2d/Canvas2D.svelte` — Add right-click handler for move-to commands
- `frontend/src/lib/canvas2d/AgentSprites.ts` — Add visual indicator for commanded agents
- `frontend/src/lib/components/ws.js` — No changes needed (send() already works)

### Approaches

1. **Simple: Director Mode Toggle + Command Queue**
   — Add a `director_mode: bool` flag to the engine. When enabled, agents check a command queue before their normal FSM. Commands are `{agent_id, command_type, payload}` dicts received via WebSocket. If a command exists, the agent executes it instead of its normal FSM cycle. Commands can be "one-shot" (single action) or "sustained" (hold position, follow, etc.). Thought injection is a special command that prepends to the LLM prompt.
   - Pros: Simple to implement, minimal changes to existing FSM, backward compatible, easy to disable
   - Cons: Polling a queue adds overhead per tick; race condition between commands and FSM transitions
   - Effort: Medium

2. **Deep: Agent Control Layer (Interceptor Pattern)**
   — Create a `DirectorController` class that sits between the tick loop and the FSM. It wraps each agent's FSM call with an interception point. At the start of each FSM tick, if director mode is on and the agent has a pending command, the controller sets `agent.active_plan`, `agent.current_action`, etc. directly and short-circuits the normal FSM. The interceptor also handles sustained commands (e.g., "hold position" prevents the FSM from moving the agent).
   - Pros: Clean separation of concerns, testable in isolation, supports sustained commands naturally
   - Cons: More code, need to be careful about which agent fields the interceptor touches vs the FSM
   - Effort: Medium-High

3. **Minimal: Mutate Agent State Directly from WebSocket**
   — Skip the director mode concept entirely. The WebSocket handler directly mutates `agent.active_plan`, `agent.current_action`, `agent.target_position`, etc. when a command arrives. The FSM naturally picks up the changes on the next tick (since `active_plan` is checked before the survival chain).
   - Pros: Very minimal code (add ~50 lines to ws.py), no FSM changes needed
   - Cons: No director mode toggle (always-on), no visual feedback, no sustained command concept, race condition risk, no separation of concerns
   - Effort: Low

### Recommendation

**Approach 1 — Director Mode Toggle + Command Queue.**

Rationale:
- It's the best balance of simplicity and safety. The director mode toggle means the simulation still runs normally when not in use.
- The command queue pattern is well-understood and avoids the complexity of an interceptor class (Approach 2).
- The engine already has the concept of `active_plan` — commanding an agent can be as simple as setting `agent.active_plan` to a single-step plan with the desired action, then letting the existing FSM execute it.
- Thought injection is naturally handled as a separate command that appends to `agent.monologue_history` and prepends to the LLM prompt on the next LLM trigger.

**Key Design Decisions:**

1. **Director Mode as Engine Flag**: `engine.director_mode: bool` (default False). When on, agents in `_fsm_evaluate()` first check `engine.command_queue.get(agent.id)`. If a command exists, execute it and skip normal FSM. If no command, fall through to normal FSM.

2. **Command Types**:
   - `move_to`: Sets `agent.target_position` and `agent.move_path`, transitions FSM to "moving"
   - `do_action`: Sets `agent.current_action`, `agent.action_duration`, `agent.action_progress=0`, transitions to "executing"
   - `set_plan`: Sets `agent.active_plan` with full plan dict (most flexible)
   - `inject_thought`: Appends to `agent.monologue_history`, sets `agent.last_thought`, triggers LLM re-evaluation
   - `release`: Clears the agent's command queue entry, returns to autonomy
   - `release_all`: Clears all command queues, exits director mode

3. **Command Flow**:
   ```
   Frontend Click/Input → ws.send({type: "command", payload: {agent_id, command, ...}})
   → WebSocket receives → dispatcher parses command type
   → engine.command_queue[agent_id] = command
   → Next tick: _fsm_evaluate() checks queue before normal flow
   → Agent executes commanded action
   → Snapshot reflects agent state → frontend updates
   ```

4. **Selection Visual**: In director mode, the selected agent's ring changes color (green→gold) and a small "👑" indicator appears near the agent.

5. **Frontend UI**: 
   - Add "Director Mode" toggle button to HUD
   - When in director mode AND agent selected: show command buttons in AgentInspector (Move Here, Gather, Rest, Chop, etc.) + thought injection textarea
   - Right-click on canvas tile: send move_to command to selected agent

6. **Thought Injection Detail**: Rather than bypassing the LLM, injected thoughts are stored in a separate `agent.injected_thoughts: list[str]` field. When the prompt is built (`RealLLMOrchestrator.build_prompt`), injected thoughts are prepended as "A voice in your head says: {thought}". This preserves the LLM pipeline while adding external influence.

### Risks

- **Race condition**: If a command arrives between FSM ticks, the agent might transition state before the command is processed. Mitigation: commands are checked at the START of `_fsm_evaluate()` before any state transitions.
- **Director mode + LLM conflicts**: If an agent is commanded while an LLM call is pending, the command should override the pending result. Mitigation: commanding an agent cancels any pending LLM future.
- **Frontend UX confusion**: Users might not understand why an agent "snaps back" to autonomy after a single commanded action. Mitigation: clear visual indicators (ring color, badge) and a "Release" button in the inspector.
- **Persistence**: Director mode state is in-memory only — lost on server restart. This is acceptable for the initial implementation.
- **LLM thought injection timing**: If agent is not in `llm_trigger` state, an injected thought won't be processed until the next LLM cycle. Mitigation: the inject_thought command can force an LLM trigger by setting `agent.last_thought` and resetting the LLM cooldown.

### Ready for Proposal

**Yes.** The exploration is complete. The orchestrator should proceed with `sdd-propose`.

Key findings to highlight in the proposal:
1. Agent selection already exists on the frontend — the biggest UI piece is already done
2. The FSM's `active_plan` check is the natural interception point — no need to rewrite the FSM
3. Command flow via existing WebSocket `send()` infrastructure
4. Thought injection should go THROUGH the LLM (not bypass it) for natural integration
5. Director mode as a toggle (not always-on) preserves existing autonomous simulation
