# Spec: agent-control

> Main spec for the agent-control domain. Originally implemented as change `agent-director-mode`.

## Purpose

Define the director mode system enabling users to temporarily override agent autonomy via WebSocket commands. When OFF, the simulation runs unchanged. When ON, the engine checks a per-agent command queue at the start of each FSM tick, executes commanded actions, and returns agents to autonomy via release. Thought injection routes through the LLM pipeline to preserve agent agency.

## Requirements

### R1 — Director Mode Toggle

| # | Specification | Strength |
|---|--------------|----------|
| R1.1 | The engine MUST maintain a `director_mode: bool` flag, default `False`. | MUST |
| R1.2 | When `director_mode` is `False`, the system SHALL have zero performance impact and SHALL NOT alter agent behavior. | SHALL |
| R1.3 | Setting `director_mode = True` MUST clear the entire command queue before enabling. | MUST |
| R1.4 | Setting `director_mode = False` MUST clear the entire command queue. | MUST |

### R2 — WebSocket Command Dispatcher

| # | Specification | Strength |
|---|--------------|----------|
| R2.1 | The backend MUST dispatch incoming WebSocket `type: "command"` messages to a command handler. | MUST |
| R2.2 | Valid command types SHALL be: `move_to`, `do_action`, `set_plan`, `inject_thought`, `release`, `release_all`. | SHALL |
| R2.3 | The dispatcher MUST validate command payload structure (agent_id, required fields per type) before enqueuing. | MUST |
| R2.4 | The dispatcher SHOULD log unrecognized command types at WARNING. | SHOULD |
| R2.5 | Command dispatching SHALL NOT block the WebSocket receive loop. | SHALL |

### R3 — Command Queue & FSM Interception

| # | Specification | Strength |
|---|--------------|----------|
| R3.1 | The engine MUST maintain `command_queue: dict[str, dict]` mapping `agent_id` → command payload. | MUST |
| R3.2 | At the START of `_fsm_evaluate()`, if `director_mode` is `True` and the agent has a queued command, the engine MUST pop the command, execute via `_execute_director_command()`, and return early (skip normal FSM). | MUST |
| R3.3 | When `move_to`, `do_action`, or `set_plan` arrives for an agent with a pending LLM future, the engine MUST cancel that future before executing the command. | MUST |
| R3.4 | When `inject_thought` arrives for an agent with a pending LLM future, the engine MUST NOT cancel the future — the thought SHALL be stored for the next LLM cycle. | MUST |
| R3.5 | One agent's command MUST NOT affect any other agent's FSM evaluation. | MUST |

### R4 — Command Type Effects

| # | Command | Effect | Strength |
|---|---------|--------|----------|
| R4.1 | `move_to(x, y)` | Set `agent.target_position`, compute pathfinder path, transition FSM to `moving`. | MUST |
| R4.2 | `do_action(action_id, target?)` | Set `agent.current_action`, compute `action_duration` via `get_action_duration()`, reset `action_progress` to 0, transition FSM to `executing`. | MUST |
| R4.3 | `set_plan(plan_dict)` | Set `agent.active_plan`, reset `plan_step_index` to 0. | MUST |
| R4.4 | `inject_thought(text)` | Append to `agent.injected_thoughts`, set `agent.last_thought`, reset LLM cooldown, force transition to `llm_trigger`. | MUST |
| R4.5 | `release` | Remove agent's entry from `command_queue`. | MUST |
| R4.6 | `release_all` | Clear entire `command_queue` AND set `director_mode = False`. | MUST |

### R5 — Thought Injection Pipeline

| # | Specification | Strength |
|---|--------------|----------|
| R5.1 | The Agent dataclass MUST gain `injected_thoughts: list[str]`, default empty. | MUST |
| R5.2 | `RealLLMOrchestrator.build_prompt()` MUST prepend each injected thought as `"A voice in your head says: {thought}"` before core prompt sections. | MUST |
| R5.3 | After prompt construction, each injected thought MUST be appended to `agent.monologue_history`. | MUST |
| R5.4 | When no LLM call is pending, `inject_thought` MUST reset the LLM cooldown timer and force the agent to `llm_trigger`. | MUST |

### R6 — Frontend UI & Visual Indicators

| # | Specification | Strength |
|---|--------------|----------|
| R6.1 | The HUD MUST render a "Director Mode" toggle button. | MUST |
| R6.2 | When director mode is ON and an agent is selected, the AgentInspector MUST display a command panel with: action buttons, thought injection textarea, and Release button. | MUST |
| R6.3 | Right-clicking the canvas while director mode is ON and an agent is selected MUST send a `move_to` command. | MUST |
| R6.4 | Right-click MUST be ignored when director mode is OFF (default camera pan behavior preserved). | MUST |
| R6.5 | The selection ring MUST change color from green to gold when director mode is ON. | MUST |
| R6.6 | Commanded agents SHOULD display a visual badge or indicator. | SHOULD |

## Scenarios

### S1: Move agent via right-click
- GIVEN director mode is ON and an agent is selected
- WHEN the user right-clicks a tile at (15, 20)
- THEN a `move_to` command is sent, `agent.target_position` is set to (15, 20), a pathfinder path is computed, and the FSM transitions to `moving`

### S2: Force agent action via command panel
- GIVEN director mode is ON and an agent is selected
- WHEN the user clicks "Chop" in the command panel
- THEN `agent.current_action` is set to `CHOP`, `action_duration` is computed, `action_progress` resets to 0, and the FSM transitions to `executing`

### S3: Inject thought reflected in monologue
- GIVEN director mode is ON and an agent is selected
- WHEN the user injects "Go talk to Ena about food"
- THEN `agent.injected_thoughts` contains the text, the next LLM prompt includes `"A voice in your head says: Go talk to Ena about food"`, and the thought is appended to `monologue_history`

### S4: Release agent back to autonomy
- GIVEN an agent with a pending command in the queue
- WHEN the user clicks "Release" for that agent
- THEN the agent's `command_queue` entry is removed, and the next FSM tick resumes normal autonomous evaluation

### S5: Toggle director mode off releases all
- GIVEN director mode is ON with 3 commanded agents
- WHEN the user toggles director mode OFF
- THEN `director_mode` is `False`, the entire `command_queue` is cleared, and all agents return to autonomy

### S6: Command arrives while LLM pending
- GIVEN an agent in `llm_waiting` state with `agent.llm_call_pending = True`
- WHEN a `move_to` command arrives for that agent
- THEN the pending LLM future is cancelled, and the command is executed on the next FSM tick

### S7: Right-click ignored when director mode off
- GIVEN director mode is OFF and an agent is selected
- WHEN the user right-clicks the canvas
- THEN no `move_to` command is sent (camera pan behavior unchanged)

### S8: Director mode toggle unaffected for other agents
- GIVEN two agents A and B, with A having a queued command
- WHEN director mode is toggled OFF
- THEN both A's and B's queue entries are cleared, and both agents resume autonomous FSM

### S9: Injected thought waits for pending LLM
- GIVEN an agent in `llm_waiting` with a pending LLM future
- WHEN an `inject_thought` command arrives
- THEN the LLM future is NOT cancelled, the thought is stored in `injected_thoughts`, and it is processed on the next LLM cycle after the current call completes

## Implementation Notes

### Auto-Enable Mechanism
The `command_dispatcher()` in `ws.py` auto-enables director mode on the backend when the first valid command (excluding `release_all`) arrives and `engine.director_mode` is currently `False`. This means the frontend HUD toggle only updates local UI state — the backend is activated on first use. The auto-enable also clears any stale command queue entries, satisfying R1.3.

### Key Architecture Decisions
- **Engine-level flag**: Single `director_mode` bool on engine, not per-agent (D4)
- **One-shot commands**: All commands are one-shot — agents return to autonomy after one tick unless re-commanded (D5)
- **In-memory only**: Director mode state is not persisted (D6)
- **LLM routing**: Injected thoughts go through the LLM pipeline as "A voice in your head says: ..." (D2)
