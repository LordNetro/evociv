# Proposal: Agent Director Mode

**Change**: agent-director-mode
**Phase**: propose
**Date**: 2026-05-03
**Author**: SDD Orchestrator (Propose Agent)
**Artifact Store**: Hybrid (engram + filesystem)

---

## 1. Intent

Allow the user to **take direct control of individual agents** in the simulation — send real-time movement commands, trigger specific actions, inject thoughts into an agent's LLM pipeline, and release agents back to full autonomy. This transforms the simulation from a purely autonomous sandbox into a **director-and-actor** model where the user can orchestrate specific behaviors while the rest of the simulation continues running naturally.

---

## 2. Scope

### IN Scope

- **Director Mode Toggle**: A global on/off switch on the engine. When OFF, the simulation runs fully autonomous as it does today. When ON, the engine checks a command queue before each agent's FSM tick.
- **Command Queue**: A per-agent queue checked at the START of `_fsm_evaluate()`, before any normal FSM logic. Commands override the current tick.
- **Command Types**:
  - `move_to` — set target position and path, transition agent to `moving` state
  - `do_action` — force an immediate action (gather, chop, rest, build, etc.)
  - `set_plan` — push a full plan dict (most flexible, for advanced use)
  - `inject_thought` — append a thought to agent's monologue, trigger LLM re-evaluation
  - `release` — clear a single agent's command queue entry, return to autonomy
  - `release_all` — clear all command queues AND exit director mode
- **WebSocket Command Dispatcher**: Process incoming `type: "command"` messages from the frontend.
- **Frontend UI**:
  - Director Mode toggle button in HUD
  - Command panel in AgentInspector when in director mode (action buttons + thought input)
  - Right-click on canvas to send `move_to` to selected agent
  - Visual indicator changes (selection ring color, badge icon) when in director mode
- **Thought Injection Through LLM Pipeline**: Injected thoughts are prepended to the prompt as "A voice in your head says: {thought}" — they influence but do not bypass the LLM.
- **Command Cancels Pending LLM**: If a command arrives while an LLM call is pending, the pending future is cancelled and the command takes priority.

### OUT Scope

- **No sustained/sustained commands** (e.g., "follow this agent", "hold position indefinitely") — all commands are one-shot. Agents return to autonomy after one commanded action unless re-commanded.
- **No director mode persistence** — state is in-memory only, lost on server restart.
- **No multi-agent selection** — only single-agent control via existing selection system.
- **No command history/replay** — commands are executed and discarded.
- **No scheduling** — no "do this in 5 seconds" type delayed commands.
- **No AI Director** — this is a user-directs-agent mode, not an AI-driven game master.

---

## 3. User Stories

### US-1: Manual Movement
> As a user, I want to click on an agent, toggle director mode, right-click on a distant tile, and watch the agent pathfind to that location — overriding whatever it was doing.

### US-2: Force Action
> As a user, I want to select an agent in director mode and click "Chop Tree" (or "Gather", "Rest", "Build") to make them perform that action immediately, ignoring their autonomous priorities.

### US-3: Thought Injection
> As a user, I want to type "Go talk to Ena about the food shortage" into an agent's command panel, and see the agent incorporate that thought into its next LLM interaction — including it in its monologue and potentially changing its behavior.

### US-4: Release to Autonomy
> As a user, I want to click "Release" on a commanded agent and see it return to normal autonomous behavior immediately, picking up from wherever the FSM decides.

### US-5: Exit Director Mode
> As a user, I want to toggle director mode OFF and have ALL agents immediately released to full autonomy, with no lingering commanded state.

---

## 4. Approach

**Director Mode Toggle + Command Queue** (as recommended by exploration).

### Architecture

```
┌─────────────────────────────────────────────────┐
│                   Frontend                       │
│  HUD toggle ──→ uiStore.directorMode             │
│  Right-click ──→ Canvas2D click handler          │
│  Command panel ──→ AgentInspector                │
│         │                                        │
│         ▼                                        │
│    ws.send({ type: "command", payload })          │
└──────────────────┬──────────────────────────────┘
                   │ WebSocket
                   ▼
┌─────────────────────────────────────────────────┐
│              Backend (ws.py)                     │
│  receive_json() → command_dispatcher()           │
│         │                                        │
│         ▼                                        │
│    engine.command_queue[agent_id] = cmd          │
└──────────────────┬──────────────────────────────┘
                   │ Next tick
                   ▼
┌─────────────────────────────────────────────────┐
│           Engine (engine.py)                     │
│  _fsm_evaluate() for each agent:                 │
│    1. IF director_mode AND command in queue      │
│       → execute command, skip normal FSM         │
│    2. ELSE → normal FSM (unchanged)              │
│         │                                        │
│         ▼                                        │
│    snapshot → broadcast to clients               │
└─────────────────────────────────────────────────┘
```

### Flow per Command Type

| Command | FSM Effect | Agent Fields Touched |
|---------|-----------|---------------------|
| `move_to(x, y)` | Transition to `moving` | `target_position`, `move_path` |
| `do_action(action_id)` | Transition to `executing` | `current_action`, `action_duration`, `action_progress` |
| `set_plan(plan_dict)` | Transition to plan execution | `active_plan`, `plan_step_index` |
| `inject_thought(text)` | Force `llm_trigger` if not waiting | `monologue_history`, `last_thought`, `injected_thoughts`, reset LLM cooldown |
| `release` | Clear agent's queue entry | `command_queue[agent_id]` deleted |
| `release_all` | Exit director mode + clear all | `director_mode = False`, entire queue cleared |

### Thought Injection Detail

The exploration uncovered a critical design point: **injected thoughts must go THROUGH the LLM pipeline, not bypass it**. Implementation:

1. Add `agent.injected_thoughts: list[str]` — a separate list from `monologue_history`
2. In `RealLLMOrchestrator.build_prompt()`, prepend each injected thought as:
   > *"A voice in your head says: {thought}"*
3. After building the prompt, append the thought to `monologue_history` (so it persists)
4. The `inject_thought` command sets `agent.last_thought`, resets the LLM cooldown timer, and if the agent is not in `llm_trigger` state, forces a transition to it
5. The LLM then processes the thought naturally as part of its context — it can accept, reject, or reflect on it

This preserves the LLM's agency while providing external influence — the agent might ignore the "voice" if it conflicts with its personality/goals.

---

## 5. Key Technical Decisions

### 5.1 Director Mode as Engine Flag

- **Decision**: `engine.director_mode: bool` (default `False`)
- **Rationale**: Simple boolean check. When `False`, the command queue is never checked — zero performance impact when not in use. The flag is settable via WebSocket command.
- **Tradeoff**: All-or-nothing toggle. No per-agent director mode. This is acceptable because the user either wants control or they don't.

### 5.2 Command Queue Checked at START of `_fsm_evaluate()`

- **Decision**: Insert the command check as the FIRST operation in `_fsm_evaluate()`, before the feed-child check, before the survival chain, before everything.
- **Rationale**: If the user sends a `release` command while an agent is executing, we need to catch it before the FSM commits to the next action. Checking at the START ensures commands are always processed on the next tick after arrival.
- **Implementation**:
  ```python
  def _fsm_evaluate(self, agent):
      # NEW: Director mode command check
      if self.director_mode and agent.id in self.command_queue:
          command = self.command_queue.pop(agent.id)
          self._execute_director_command(agent, command)
          return  # Skip normal FSM this tick

      # ... existing FSM logic follows unchanged ...
  ```

### 5.3 Command Types

- `move_to`: `{"type": "move_to", "x": int, "y": int}` — sets `agent.target_position`, calculates path via existing pathfinding, transitions to `moving`
- `do_action`: `{"type": "do_action", "action_id": str, "target": optional dict}` — sets `agent.current_action`, `agent.action_duration`, resets progress, transitions to `executing`
- `set_plan`: `{"type": "set_plan", "plan": dict}` — sets `agent.active_plan`, resets `plan_step_index` to 0, transitions to plan execution
- `inject_thought`: `{"type": "inject_thought", "text": str}` — appends to `injected_thoughts`, forces LLM trigger
- `release`: `{"type": "release"}` — pops agent from command queue, no further effect
- `release_all`: `{"type": "release_all"}` — sets `director_mode = False`, clears entire queue

### 5.4 Injected Thoughts Go Through LLM Pipeline

- **Decision**: Injected thoughts are prepended to the system prompt as third-party influence, not injected directly into agent state.
- **Rationale**: Bypassing the LLM breaks the simulation's internal consistency — the agent acts without "thinking." By routing through the LLM, the thought becomes a genuine influence that the agent can integrate or reject based on its persona, memories, and context.
- **Implementation**: New `agent.injected_thoughts` list + prompt modification in `RealLLMOrchestrator`.

### 5.5 Command Cancels Pending LLM Calls

- **Decision**: When any command arrives for an agent that has `agent.llm_call_pending = True` and a non-None `agent.llm_future`, cancel the future.
- **Rationale**: If the user takes control, they don't want the agent's autonomously-generated LLM plan to execute after the command. The command should take full priority.
- **Implementation**: In `_execute_director_command()`, check and cancel pending LLM futures before applying the command.

### 5.6 Frontend: Toggle in HUD, Panel in AgentInspector, Right-Click Move

- **Decision**: Three UI entry points:
  1. **HUD toggle**: A simple button showing "Director: OFF" / "Director: ON" that sends a `release_all` (when turning off) or sets director mode (when turning on)
  2. **AgentInspector command panel**: When director mode is ON and an agent is selected, show action buttons (Move Here, Gather, Chop, Rest, Build, etc.) + a thought injection textarea
  3. **Right-click on canvas**: When director mode is ON and an agent is selected, right-clicking on a tile sends `move_to` to that agent
- **Rationale**: The exploration confirmed agent selection already works, the HUD already exists, and `ws.send()` is already wired. These are additive UI changes with no refactoring needed.

### 5.7 Visual Indicators for Director Mode

- **Decision**: Change the selection ring from green to gold when in director mode. Add a small crown/badge icon near commanded agents.
- **Rationale**: Users need immediate visual feedback that they are in "control mode" and which agents are commanded vs autonomous.

---

## 6. Affected Areas

### Backend Files (Changes)

| File | Change Type | Description |
|------|------------|-------------|
| `backend/app/api/ws.py` | **Major** | Replace command placeholder with full `command_dispatcher()` that routes `type: "command"` messages to `engine.command_queue` |
| `backend/app/simulation/engine.py` | **Major** | Add `director_mode: bool`, `command_queue: dict`, `_execute_director_command()` method, FSM interception in `_fsm_evaluate()` |
| `backend/app/simulation/agent.py` | **Minor** | Add `injected_thoughts: list[str]` field to `Agent` class |
| `backend/app/models/schemas.py` | **Minor** | Add `ClientCommand` schema with validated command types |
| `backend/app/simulation/snapshot.py` | **Minor** | Optionally expose `director_mode` and per-agent `is_commanded` state in snapshots |
| `backend/app/main.py` | **None** | No changes expected (engine lifecycle not affected) |

### Frontend Files (Changes)

| File | Change Type | Description |
|------|------------|-------------|
| `frontend/src/lib/stores/uiStore.svelte.js` | **Minor** | Add `directorMode`, `selectedCommandTarget` runes |
| `frontend/src/lib/components/HUD.svelte` | **Minor** | Add Director Mode toggle button |
| `frontend/src/lib/components/AgentInspector.svelte` | **Major** | Add command panel: action buttons, thought textarea, release button |
| `frontend/src/lib/canvas2d/Canvas2D.svelte` | **Minor** | Add right-click handler for `move_to` commands |
| `frontend/src/lib/canvas2d/OverlayLayer.ts` | **Minor** | Change selection ring color (green → gold) when in director mode |
| `frontend/src/lib/canvas2d/AgentSprites.ts` | **Minor** | Add visual badge/indicator for commanded agents |
| `frontend/src/lib/components/ws.js` | **None** | No changes needed (send() already works) |

### Tests (New/Updated)

| File | Description |
|------|-------------|
| `backend/tests/test_director_mode.py` | New test file: command queue, command types, FSM interception, thought injection, release, edge cases |
| Existing FSM tests | Updates to verify director mode flag does not affect normal FSM when OFF |

---

## 7. Rollback Plan

### Scenario A: Implementation introduces FSM regression

- **Revert strategy**: The director mode changes are purely additive in `_fsm_evaluate()`. The insertion point is at the **start** of the method, with an early return. Everything below is unchanged.
- **Rollback**: Delete the director-mode check block at the top of `_fsm_evaluate()`. Remove `director_mode` and `command_queue` from the engine. Remove `_execute_director_command()`. Delete the WebSocket dispatcher additions. This restores the original FSM behavior completely.
- **Confidence**: HIGH — the changes add code before existing logic without modifying it.

### Scenario B: WebSocket command processing breaks existing message types

- **Revert strategy**: The command dispatcher only processes `type: "command"` messages. Existing `type: "config_change"` and `type: "agent_edit"` paths are untouched.
- **Rollback**: Remove the `if msg.type == "command"` block in `ws.py`. All existing WS functionality remains intact.
- **Confidence**: HIGH — additive change to a switch statement.

### Scenario C: Thought injection breaks LLM prompt building

- **Revert strategy**: The `injected_thoughts` addition to `RealLLMOrchestrator.build_prompt()` is a prepend operation. If it causes issues, remove the prepend block and the `agent.injected_thoughts` field.
- **Rollback**: Remove the injected_thoughts handling from `build_prompt()`. The field can remain on the Agent model without being used (zero runtime impact).
- **Confidence**: MEDIUM — depends on prompt structure complexity.

### Full Rollback Commands

```
git revert <commit-hash> --no-edit
git push
```

Or, for partial rollback before committing:
```
git checkout -- backend/app/api/ws.py backend/app/simulation/engine.py
git checkout -- frontend/src/lib/components/AgentInspector.svelte
git checkout -- frontend/src/lib/components/HUD.svelte
# ... etc for each changed file
```

---

## 8. Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **Race condition**: Command arrives between FSM ticks, agent transitions before command is processed | Low — command delayed by 1 tick | Medium | Check queue at START of `_fsm_evaluate()` before any logic. Worst case: 1 tick delay, which is imperceptible at 10+ FPS |
| **LLM conflict**: Commanded agent has pending LLM call — the LLM response arrives mid-command | Agent executes autonomously-generated plan after command | Low | Cancel pending LLM future when command arrives. The LLM result is discarded |
| **UX confusion**: User doesn't understand agents "snap back" to autonomy after one command | Frustration, perceived bug | High | Visual indicators (ring color, badge), clear label in AgentInspector showing "Commanded" vs "Autonomous", explicit "Release" button |
| **Right-click conflict**: Right-click used for both camera pan and move-to | Broken camera controls | Medium | Only intercept right-click when director mode is ON AND an agent is selected. Default is camera pan as before |
| **Thought injection timing**: Agent not in `llm_trigger` state when thought arrives | Thought ignored until next LLM cycle | Medium | Force LLM trigger: reset cooldown, set `last_thought`, transition to `llm_trigger` state |
| **Director mode + multiple agents**: User sends commands to multiple agents rapidly | Command queue grows, older commands stale | Low | Each agent has independent queue entry. New commands overwrite old ones for the same agent |
| **Persistence**: Director mode state is in-memory only | Lost on server restart | Low | Acceptable for initial implementation. Documented as a known limitation |

---

## 9. Summary

The Agent Director Mode adds **direct user control** over individual agents in the simulation through a toggleable director mode. When active, the engine checks a per-agent command queue at the start of each FSM tick. Commands include movement, actions, plan override, thought injection, and release. The approach is intentionally minimal — it leverages the existing `active_plan` interception point in the FSM, the existing WebSocket `send()` infrastructure, and the existing agent selection UI. Thought injection differs from a simple state override: it routes through the LLM pipeline as "a voice in your head," preserving the agent's agency while providing external influence.

The feature is **fully backward compatible** — when director mode is OFF (the default), there is zero performance impact and no behavioral change.
