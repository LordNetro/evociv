# Evociv — Simulation Loop & FSM

> **Version:** 1.0.0
> **Last Updated:** 2026-04-28

---

## 1. The Main Loop (Backend)

```
1 tick = 100ms (10 ticks/sec, configurable)

EVERY TICK:
  1. TIMER: Increment hunger/thirst/energy for all agents
  2. FSM: Update each agent's state machine
  3. QUEUE: Process the event queue
  4. LLM: Evaluate pending LLM responses (async)
  5. WORLD: Update environment (resource regeneration, time of day)
  6. METRICS: Compile global simulation metrics
  7. SEND: Build and broadcast delta snapshot via WebSocket
```

### Pseudocode

```python
class SimulationEngine:
    def __init__(self, world_config: WorldConfig):
        self.world = World(world_config)
        self.agents = [Agent.from_config(c) for c in world_config.agents]
        self.event_queue = EventQueue()
        self.llm_orchestrator = LLMOrchestrator()
        self.tick = 0
        self.running = False
    
    async def tick(self):
        self.tick += 1
        
        # 1. Update physical needs
        for agent in self.agents:
            agent.hunger += HUNGER_DECAY_RATE
            agent.thirst += THIRST_DECAY_RATE
            agent.energy -= ENERGY_DECAY_RATE
        
        # 2. Run FSM for each agent
        for agent in self.agents:
            self._run_fsm(agent)
        
        # 3. Process event queue (encounters, discoveries, etc.)
        events = self.event_queue.drain()
        for event in events:
            affected = self._get_agents_at(event.position)
            for agent in affected:
                agent.fsm.trigger_event(event)
        
        # 4. Check for pending LLM responses
        ready = self.llm_orchestrator.poll_completed()
        for agent_id, response in ready:
            agent = self._get_agent(agent_id)
            if response.success:
                agent.active_plan = Plan.from_json(response.data)
                agent.fsm.transition_to("moving")
            else:
                agent.fallback_to_instinct()
        
        # 5. Update world
        self.world.regenerate_resources()
        self.world.advance_time()
        
        # 6. Metrics
        metrics = self._compute_metrics()
        
        # 7. Broadcast (delta snapshot)
        snapshot = self._build_snapshot(metrics)
        await self.ws_manager.broadcast(snapshot)
    
    def _run_fsm(self, agent: Agent):
        match agent.fsm.current_state:
            case "idle":
                self._fsm_idle(agent)
            case "moving":
                self._fsm_moving(agent)
            case "executing":
                self._fsm_executing(agent)
            case "evaluate":
                self._fsm_evaluate(agent)
            case "llm_trigger":
                self._fsm_llm_trigger(agent)
            case "llm_waiting":
                self._fsm_llm_waiting(agent)
```

---

## 2. Agent FSM — State Details

```
                    ┌─────────────┐
                    │    IDLE     │ ◄──────────┐
                    └──────┬──────┘            │
                           │ Has critical need?│
                    ┌──────┴──────┐            │
           ┌────────┤  EVALUATE   ├────────────┘
           │        └──────┬──────┘     Plan still valid?
           │ Needs LLM     │ FSM can handle
     ┌─────┴─────┐   ┌─────┴──────┐
     │LLM_TRIGGER│   │   MOVING   │
     └─────┬─────┘   └─────┬──────┘
           │ Async call     │ Arrived
     ┌─────┴──────┐  ┌─────┴─────────┐
     │LLM_WAITING │  │  EXECUTING    │
     └─────┬──────┘  └─────┬─────────┘
           │ Response back │ Action done
           └───────┬───────┘
                   │
              ┌────┴────┐
              │ IDLE    │ (or next step → MOVING)
              └─────────┘
```

### 2.1 IDLE

- Agent has no plan or just completed one.
- **Evaluate**: Check physical needs against thresholds:
  - `hunger < 30%` AND `berries_nearby` → MOVING (to berries)
  - `thirst < 30%` AND `water_nearby` → MOVING (to water)
  - `energy < 20%` → EXECUTING (rest)
  - None of the above → EVALUATE (to check if plan needed)

### 2.2 MOVING

- **Interpolation**: Each tick, `progress += 1.0 / total_ticks`
- **Render**: Frontend interpolates position at 60 FPS
- **Interruption**: If `critical_need` triggers mid-move, abort → EVALUATE
- **Arrival**: When `progress >= 1.0` → EXECUTING

```python
def _fsm_moving(self, agent: Agent):
    step = agent.active_plan.steps[agent.plan_step_index]
    agent.move_progress += 1.0 / step.estimated_ticks
    
    if agent.move_progress >= 1.0:
        agent.position = step.target
        agent.move_progress = 0.0
        agent.fsm.transition_to("executing")
```

### 2.3 EXECUTING

- Perform the current action.
- Each tick: `action_progress += 1.0 / duration_ticks`.
- **On completion**:
  - Apply effects (add to inventory, modify stats)
  - If more steps remain → MOVING (to next step's target)
  - If all steps done → EVALUATE

```python
def _fsm_executing(self, agent: Agent):
    step = agent.active_plan.steps[agent.plan_step_index]
    agent.action_progress += 1.0 / step.estimated_ticks
    
    if agent.action_progress >= 1.0:
        self._apply_action_effects(agent, step)
        agent.action_progress = 0.0
        agent.plan_step_index += 1
        
        if agent.plan_step_index < len(agent.active_plan.steps):
            agent.fsm.transition_to("moving")
        else:
            agent.fsm.transition_to("evaluate")
```

### 2.4 EVALUATE

- Check if the plan is still valid:
  - Does the target resource still exist?
  - Are the needs still within acceptable range?
  - Is the plan still relevant given current context?
- **Plan valid** → Continue (IDLE → next FSM cycle picks it up)
- **Plan invalid** or **Plan completed**:
  - If critical need exists → handle with FSM (instinct)
  - If no clear path → LLM_TRIGGER

### 2.5 LLM_TRIGGER

- Queue an async call to the LLM orchestrator.
- Contains: agent's system prompt + current state + recent memories.
- Agent transitions to LLM_WAITING.
- **Note**: this is non-blocking. The agent continues with instinct behavior while waiting.

```python
async def _fsm_llm_trigger(self, agent: Agent):
    if not agent.llm_call_pending:
        prompt = self.llm_orchestrator.build_prompt(agent)
        agent.llm_call_pending = True
        asyncio.create_task(
            self.llm_orchestrator.call_async(agent.id, prompt)
        )
    agent.fsm.transition_to("llm_waiting")
```

### 2.6 LLM_WAITING

- Agent has no active plan (waiting for LLM).
- **Default behavior**: instinct — find nearest food/water and consume.
- **On LLM response**: parse JSON plan, validate, set as active plan.
  - If valid → MOVING (start step 0)
  - If invalid/malformed → retry once, then instinct fallback
- **Timeout**: if no response in 30s, agent falls back to instinct indefinitely.

---

## 3. Event-Driven LLM Triggers

### Trigger Conditions

```python
def _should_trigger_llm(self, agent: Agent) -> bool:
    """Returns True if agent needs LLM consultation."""
    
    # 1. Plan just completed and no obvious next action
    if agent.fsm.current_state == "evaluate" and agent.active_plan is None:
        return True
    
    # 2. Critical need and no plan to address it
    if (agent.hunger < CRITICAL_THRESHOLD or agent.thirst < CRITICAL_THRESHOLD):
        if not agent.active_plan or not self._plan_addresses_needs(agent):
            return True
    
    # 3. Social encounter (filtered by sociability)
    nearby = self.world.get_agents_in_radius(agent.position, INTERACTION_RADIUS)
    if len(nearby) > 1:  # Including self
        # Higher sociability = more likely to engage
        chance = agent.sociability / 100.0
        if random.random() < chance:
            return True
    
    # 4. Discovery (new type of resource or structure)
    if agent.just_discovered_novel_entity:
        return True
    
    # 5. External stimulus
    if agent.pending_external_stimulus:
        return True
    
    # 6. Periodic reflection (every ~60 seconds of sim time)
    if agent.ticks_since_last_llm > REFLECTION_INTERVAL:
        return True
    
    return False
```

### Prompt Construction

```python
def build_prompt(self, agent: Agent) -> str:
    return f"""
[SYSTEM]
{agent.system_prompt}

[CURRENT STATE]
- Position: {agent.position}
- Hunger: {agent.hunger:.1f}%
- Thirst: {agent.thirst:.1f}%
- Energy: {agent.energy:.1f}%
- Health: {agent.health:.1f}%
- Inventory: {agent.inventory}

[NEARBY]
- Resources: {self.world.get_nearby_resources(agent.position)}
- Agents: {self.world.get_nearby_agents(agent.position)}
- Structures: {self.world.get_nearby_structures(agent.position)}

[MEMORIES]
{self.memory.get_relevant(agent.id, top_k=3)}

[TRIGGER]
{agent.last_trigger_event}

[INSTRUCTIONS]
Respond with a JSON plan following this exact schema:
{json_schema}
"""
```

---

## 4. Frontend Render Loop

```typescript
// render-loop.ts — runs at 60 FPS via requestAnimationFrame

class RenderEngine {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private agents: Map<string, InterpolatedAgent>;
  private lastSnapshot: WorldSnapshot | null;
  
  // Easing function for smooth movement
  private lerp(a: number, b: number, t: number): number {
    return a + (b - a) * t;
  }
  
  // Called when a new snapshot arrives from WebSocket
  onSnapshot(snapshot: WorldSnapshot): void {
    for (const [id, state] of Object.entries(snapshot.agents)) {
      let agent = this.agents.get(id);
      if (!agent) {
        agent = new InterpolatedAgent(id);
        this.agents.set(id, agent);
      }
      // Set target positions — the render loop will lerp toward these
      agent.targetX = state.position[0];
      agent.targetY = state.position[1];
      agent.targetEmoji = state.current_action_emoji;
      agent.targetActionProgress = state.action_progress;
      agent.hunger = state.hunger;
      agent.thirst = state.thirst;
    }
    
    // Remove dead agents
    for (const id of snapshot.removed_agents) {
      this.agents.delete(id);
    }
  }
  
  // Called every frame (60 FPS)
  render(timestamp: number, deltaMs: number): void {
    const ctx = this.ctx;
    const interpolationFactor = Math.min(deltaMs * 0.01, 1); // Smooth factor
    
    // Clear
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    
    // Draw grid
    this.drawGrid(ctx);
    
    // Draw resources
    this.drawResources(ctx, this.lastSnapshot?.tiles ?? []);
    
    // Draw agents (interpolated)
    ctx.save();
    for (const agent of this.agents.values()) {
      // Interpolate position
      agent.currentX = this.lerp(agent.currentX, agent.targetX, interpolationFactor);
      agent.currentY = this.lerp(agent.currentY, agent.targetY, interpolationFactor);
      
      // Interpolate action progress
      agent.currentActionProgress = this.lerp(
        agent.currentActionProgress, 
        agent.targetActionProgress, 
        interpolationFactor
      );
      
      this.drawAgent(ctx, agent);
    }
    ctx.restore();
    
    // Draw UI overlay (health bars, emojis)
    this.drawAgentOverlays(ctx);
  }
  
  private drawAgent(ctx: CanvasRenderingContext2D, agent: InterpolatedAgent): void {
    const x = agent.currentX * TILE_SIZE;
    const y = agent.currentY * TILE_SIZE;
    const radius = 12;
    
    // Shadow
    ctx.beginPath();
    ctx.arc(x + 2, y + 2, radius, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(0, 0, 0, 0.2)";
    ctx.fill();
    
    // Body (color by role)
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fillStyle = ROLE_COLORS[agent.role];
    ctx.fill();
    ctx.strokeStyle = ROLE_BORDERS[agent.role];
    ctx.lineWidth = 2;
    ctx.stroke();
    
    // Emoji above agent (fade in/out)
    if (agent.currentEmoji) {
      ctx.font = "14px serif";
      ctx.textAlign = "center";
      ctx.globalAlpha = agent.emojiOpacity;
      ctx.fillText(agent.currentEmoji, x, y - radius - 8);
      ctx.globalAlpha = 1.0;
    }
  }
}
```

---

## 5. Performance Considerations

### Backend

| Concern | Solution |
|---------|----------|
| LLM latency (1-30s) | Async calls, non-blocking. Agent uses instinct while waiting. |
| Tick duration > 100ms | Configurable tick rate. Default to 100ms, can slow to 500ms. |
| Memory growth | Agent histories capped at last N entries. SQLite for long-term. |

### Frontend

| Concern | Solution |
|---------|----------|
| 60 FPS rendering | `requestAnimationFrame`, no forced layout. |
| Canvas repaint cost | Only redraw changed entities. Dirty rect tracking if needed. |
| WebSocket flood | Delta snapshots only. Configurable send interval. |
| Large agent counts | Spatial hash for culling off-screen agents. LOD rendering. |
