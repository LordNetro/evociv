# Design: Agent Director Mode

## Technical Approach

Insert a **command queue** as a pre-check in `_fsm_evaluate()` — when director mode is ON and an agent has a queued command, execute it and skip the normal FSM. Commands arrive via WebSocket `type: "command"` messages, dispatched by a new `command_dispatcher()` in `ws.py`. Injected thoughts route through the LLM pipeline ("a voice in your head") to preserve agent agency. All UI changes are additive: a toggle in HUD, a command panel in AgentInspector, right-click move on canvas, and visual indicator changes in the PixiJS layers.

---

## Architecture Overview

```
Frontend (SvelteKit)
  HUD toggle ──→ uiStore.directorMode
  Right-click ──→ Canvas2D click handler
  Command panel ──→ AgentInspector buttons
    │
    ▼ ws.send({ type: "command", payload })
    │
WebSocket ──→ ws.py: command_dispatcher()
    │           validates, logs, enqueues
    ▼
engine.command_queue[agent_id] = cmd
    │
    ▼ (next tick)
engine._fsm_evaluate():
  1. IF director_mode AND agent.id IN command_queue
     → _execute_director_command(), RETURN
  2. ELSE → normal FSM (unchanged)
    │
    ▼
  snapshot → broadcast
```

---

## Data Flow Per Command

| Command | Source UI | WS Payload | Engine Method | FSM Transition |
|---------|-----------|------------|--------------|----------------|
| `move_to` | Canvas right-click | `{x, y}` | `_execute_move_to` | → `moving` |
| `do_action` | AgentInspector btn | `{action_id, target?}` | `_execute_do_action` | → `executing` |
| `set_plan` | AgentInspector (advanced) | `{plan}` | `_execute_set_plan` | → `evaluate` |
| `inject_thought` | AgentInspector textarea | `{text}` | `_execute_inject_thought` | → `llm_trigger` |
| `release` | AgentInspector btn | `{}` | `_execute_release` | (none — queue entry removed) |
| `release_all` | HUD toggle OFF | `{}` | `_execute_release_all` | `director_mode = False` |

---

## Backend Design

### Engine (`engine.py`)

Add two attributes and one method:
- `director_mode: bool = False` — engine-level flag, default OFF, zero cost
- `command_queue: dict[str, dict] = field(default_factory=dict)` — per-agent commands

Insert at the **start** of `_fsm_evaluate()`:

```python
def _fsm_evaluate(self, agent, fsm, tick):
    # ── NEW: Director mode command check (BEFORE everything) ──
    if self.director_mode and agent.id in self.command_queue:
        cmd = self.command_queue.pop(agent.id)
        self._execute_director_command(agent, cmd)
        return  # Skip normal FSM this tick

    # ... existing FSM logic unchanged ...
```

`_execute_director_command(self, agent, cmd)` dispatches by `cmd["type"]`. Before any command except `inject_thought`, cancel the pending LLM future if it exists and is not done.

### WebSocket (`ws.py`)

Replace the command placeholder in `websocket_endpoint`:

```python
data = await websocket.receive_json()
if data.get("type") == "command":
    engine = websocket.app.state.engine
    command_dispatcher(data, engine)
```

New function `command_dispatcher(msg, engine)`:
- Validates `command_type` ∈ allowed set, logs WARNING on unknown
- Enqueues to `engine.command_queue[agent_id] = payload`
- `release_all` also sets `engine.director_mode = False`
- Non-blocking: synchronous dispatch, no `await`

### Agent (`agent.py`)

Add `injected_thoughts: list[str] = field(default_factory=list)` to `@dataclass Agent`.

### LLM Pipeline (`orchestrator.py`)

In `build_prompt()`: after existing prompt construction, prepend each injected thought:

```python
for thought in agent.injected_thoughts:
    prompt = f"A voice in your head says: {thought}\n\n{prompt}"
    agent.monologue_history.append(thought)
agent.injected_thoughts.clear()
```

### Schemas (`schemas.py`)

Add `ClientCommand` model:

```python
class ClientCommand(BaseModel):
    type: Literal["move_to", "do_action", "set_plan", "inject_thought", "release", "release_all"]
    agent_id: str
    payload: dict
```

### Snapshot (`snapshot.py`)

Optionally include `director_mode` in snapshot payload. In `WorldSnapshot`, add `director_mode: bool = False`. In `_build_agent_state`, add `is_commanded: bool = agent.id in engine.command_queue`. The snapshot builder needs access to the engine's command queue — pass during construction or as a build parameter.

---

## Frontend Design

### Store (`uiStore.svelte.js`)

Add Svelte rune or writable:
```js
directorMode: false   // boolean toggle
```
Will be toggled by HUD button and read by AgentInspector, Canvas2D, OverlayLayer, AgentSprites.

### HUD (`HUD.svelte`)

Add toggle button next to Pause/Resume:
```
[Director: OFF]  (gray)
[Director: ON]   (gold)
```
Sends `release_all` when toggling OFF. When ON, just sets `uiStore.directorMode = true`.

### AgentInspector

When `directorMode === true` AND agent selected, show command panel:
- Action buttons grid: Gather 🌾 Chop 🪓 Rest 💤 Build 🔧 Mine ⛏️ Guard 🛡️
- Thought injection textarea + "Inject" send button
- "Release" button (sends `release` for this agent)
- `inject_thought` sends via ws.send immediately
- Label: "Commanded" (gold badge) vs "Autonomous" (gray)

### Canvas Changes

- **Canvas2D.svelte**: Right-click handler — if `directorMode && selectedAgentId`, prevent default, convert pixel coords to grid tile, send `move_to` via ws.send. Otherwise, let camera pan through.
- **OverlayLayer.ts**: Accept `directorMode` parameter, change `RING_COLOR` from `0x00ff88` (green) to `0xffd700` (gold) when active.
- **AgentSprites.ts**: Draw a small gold crown/badge indicator on sprites whose agent_id is in commanded agents set. Accept commanded set from snapshot or store.

---

## Architecture Decisions

### D1: Command queue in `_fsm_evaluate()` not in `_run_agent_fsm`

| Option | Tradeoff |
|--------|----------|
| In `_run_agent_fsm` | Requires restructuring the FSM runner; affects all states |
| In `_fsm_evaluate()` (chosen) | Single insertion point BEFORE all existing logic; zero behavioral change to existing FSM; one early return |

### D2: Injected thoughts through LLM pipeline

| Option | Tradeoff |
|--------|----------|
| Direct state injection (rejected) | Breaks internal consistency — agent acts without "thinking" |
| Through LLM (chosen) | Preserves agency; agent can accept, reject, or reflect; still visible in monologue |

### D3: Cancel pending LLM futures on command

| Option | Tradeoff |
|--------|----------|
| Let LLM complete (rejected) | User command is overridden by autonomous plan — defeats purpose |
| Cancel future (chosen) | User intent takes priority; LLM result discarded; exception: `inject_thought` does NOT cancel |

### D4: Engine-level flag, not per-agent

| Option | Tradeoff |
|--------|----------|
| Per-agent toggle (rejected) | Complexity: need per-agent state, UI for each, edge cases on mixed modes |
| Engine-level flag (chosen) | Simplest: one boolean, zero overhead when OFF, clear on/off semantics |

### D5: One-shot commands only

| Option | Tradeoff |
|--------|----------|
| Sustained commands (rejected) | State machine complexity for "follow", "hold position" — need timeouts, interruptions |
| One-shot (chosen) | Simple queue pop + execute. Agent returns to autonomy next tick if no new command |

### D6: In-memory only, no persistence

| Option | Tradeoff |
|--------|----------|
| Persist director state (rejected) | Adds DB schema, snapshot versioning, restore logic for MVP |
| In-memory only (chosen) | Zero persistence overhead; acceptable for initial implementation; documented limitation |

---

## FSM Flow

```
_fsm_evaluate() ENTRY
│
├─ [NEW] IF director_mode AND agent.id IN command_queue:
│     cmd = command_queue.pop(agent.id)
│     IF cmd.type ≠ inject_thought AND agent.llm_call_pending:
│         agent.llm_future.cancel()
│         agent.llm_call_pending = False
│     _execute_director_command(agent, cmd)
│     RETURN  ← Skip normal FSM
│
├─ [EXISTING] Shelter seeking (extreme weather)
├─ [EXISTING] Feed child check
├─ [EXISTING] Role priorities
├─ [EXISTING] Hardcoded survival chain
└─ [EXISTING] LLM trigger / plan execution
```

---

## Sequence Diagram (move_to via right-click)

```
User               Frontend              WS                    Engine                 Agent
 │                    │                    │                      │                      │
 │ right-click tile   │                    │                      │                      │
 │───────────────────►│                    │                      │                      │
 │                    │ ws.send({          │                      │                      │
 │                    │   type:"command",  │                      │                      │
 │                    │   agent_id,        │                      │                      │
 │                    │   payload:         │                      │                      │
 │                    │    {type:"move_to",│                      │                      │
 │                    │     x, y}          │                      │                      │
 │                    │───────────────────►│                      │                      │
 │                    │                    │ command_dispatcher() │                      │
 │                    │                    │ .validate            │                      │
 │                    │                    │ .enqueue             │                      │
 │                    │                    │─────────────────────►│                      │
 │                    │                    │  queue[agent]=cmd    │                      │
 │                    │                    │                      │── next tick ──►      │
 │                    │                    │                      │ _fsm_evaluate()       │
 │                    │                    │                      │ check queue           │
 │                    │                    │                      │ pop & execute         │
 │                    │                    │                      │ find_path, set target │
 │                    │                    │                      │ transition "moving"   │
 │                    │                    │                      │◄─────────────────────│
 │                    │                    │◄── snapshot ────────│                      │
 │                    │◄── update UI ─────│                      │                      │
 │  ring turns gold   │                    │                      │                      │
 │◄───────────────────│                    │                      │                      │
```

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Race: command arrives mid-tick | Med | Low (1 tick delay) | Checked at START of `_fsm_evaluate` — max 1 tick delay |
| LLM conflict: pending future vs command | Low | Med | Cancel future for all commands except `inject_thought` |
| Right-click: camera pan vs move_to | Med | Med | Only intercept in director mode + agent selected |
| Multiple rapid commands to same agent | Low | Low | Single entry per agent — new overwrites old |
| UX confusion: agents snap back to autonomy | High | High | Visual indicators (gold ring, badge), "Commanded"/"Autonomous" label |

---

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit | `_execute_director_command` dispatches correctly | Parametrized pytest on mock agent + engine |
| Unit | Command queue check at start of `_fsm_evaluate` | Test early return, verify normal FSM when queue empty |
| Unit | LLM future cancellation on command arrival | Mock asyncio.Future, verify `.cancel()` called |
| Unit | Injected thoughts prepended to prompt | Call `build_prompt()` on agent with `injected_thoughts` |
| Unit | Command payload validation | Pydantic `ClientCommand` model validation |
| Integration | WS message → command_queue | `httpx.ASGITransport` with `TestClient`, verify queue state |
| Integration | Full flow: send command → snapshot reflects changes | End-to-end engine tick with WS send |

No migration required — all new code, no existing data affected.
