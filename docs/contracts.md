# Evociv — Data Contracts & API

> **Version:** 1.0.0
> **Last Updated:** 2026-04-28

---

## 1. WebSocket Messages

### 1.1 Server → Client (`WorldSnapshot`)

Sent every N ticks (default: every tick). Partial/delta state to minimize bandwidth.

```typescript
interface ServerMessage {
  type: "snapshot" | "llm_response" | "error" | "config_ack";
  payload: WorldSnapshot | LLMResponse | ErrorPayload | ConfigAck;
}

interface WorldSnapshot {
  tick: number;
  timestamp: number;            // Unix ms
  
  // Grid changes (only tiles in viewport or that changed)
  tiles: TileUpdate[];
  
  // Agent state (full delta per agent)
  agents: Record<string, AgentState>;
  removed_agents: string[];     // Agents that died this tick
  
  // Global metrics
  metrics: SimulationMetrics;
  
  // Recent events (for UI notifications and logs)
  events: SimEvent[];
}

interface TileUpdate {
  x: number;
  y: number;
  resource_type: ResourceType | null;   // null = empty
  amount: number;                        // Resource quantity
}

type ResourceType = "tree" | "water" | "berries" | "stone" | "empty";
```

### 1.2 Client → Server

```typescript
interface ClientMessage {
  type: "command" | "config_change" | "agent_edit";
  payload: CommandPayload | ConfigChangePayload | AgentEditPayload;
}

// --- Commands ---
type CommandType = "pause" | "resume" | "set_speed" | "reset" | "step";

interface CommandPayload {
  command: CommandType;
  value?: number;      // For set_speed: 0.5 = half speed, 2 = double speed
}

// --- Config Changes ---
interface ConfigChangePayload {
  key: string;         // e.g. "tick_rate", "world_seed"
  value: unknown;
}

// --- Agent Edits (mid-simulation) ---
interface AgentEditPayload {
  agent_id: string;
  system_prompt?: string;
  attributes?: Partial<AgentAttributes>;
}
```

---

## 2. Core Data Models

### 2.1 Agent State

```python
@dataclass
class AgentState:
    id: str                          # "agent_001"
    name: str                        # "Zog"
    position: tuple[float, float]    # (x, y) grid coords
    role: str                        # "gatherer" | "builder" | "scout" | "warrior"
    
    # Physical state (0-100)
    hunger: float                    # 100 = full, 0 = starving
    thirst: float                    # 100 = hydrated, 0 = dehydrated
    energy: float                    # 100 = rested, 0 = exhausted
    health: float                    # 100 = healthy, 0 = dead
    
    # Base attributes (0-100)
    strength: int
    intelligence: int
    sociability: int
    speed: int
    
    # FSM state
    current_state: AgentFSMState     # "idle" | "moving" | "executing" | "evaluate" | "llm_trigger" | "llm_waiting"
    current_action: str | None       # Human-readable: "Moving to lake", "Chopping wood"
    current_action_emoji: str        # "💧", "🪓", "🍎", "🗣️"
    action_progress: float           # 0.0 → 1.0 (for smooth animation)
    
    # Active LLM plan
    active_plan: LLMPlan | None
    plan_step_index: int
    
    # Inventory
    inventory: dict[str, int]        # {"wood": 5, "berries": 12, "stone": 3}
    
    # Consciousness (for the UI panel)
    last_thought: str                # "I need to find water before nightfall"
    monologue_history: list[str]     # Last N internal monologues
    
    # Social
    relationships: dict[str, float]  # {"agent_002": 0.8, "agent_003": -0.3}

type AgentFSMState = "idle" | "moving" | "executing" | "evaluate" | "llm_trigger" | "llm_waiting"
```

### 2.2 LLM Plan (model output, structured JSON)

```json
{
  "reasoning": "I'm thirsty (20%) and there's water to the east. After drinking I can look for wood near the water to build a shelter.",
  "intention": "Go to the lake, drink, and establish a camp",
  "priority": "high",
  "steps": [
    {
      "action": "move",
      "target": [42, 28],
      "duration_secs": 8,
      "reason": "Water source detected"
    },
    {
      "action": "drink",
      "target": null,
      "duration_secs": 3,
      "reason": "Critical thirst"
    },
    {
      "action": "move",
      "target": [40, 30],
      "duration_secs": 5,
      "reason": "Forest near water"
    },
    {
      "action": "chop",
      "target": [40, 30],
      "duration_secs": 15,
      "reason": "Wood for shelter construction"
    }
  ],
  "abort_if": {
    "hunger < 15": "Find and eat berries",
    "thirst < 15": "Find water immediately"
  },
  "think_aloud": "This lake looks like a good spot. Water and trees nearby."
}
```

### 2.3 Action Types (FSM-executable)

| Action | Duration Logic | Effect |
|--------|---------------|--------|
| `move` | distance / speed | Position interpolation |
| `chop` | fixed (per wood unit) | Inventory.wood += N |
| `drink` | fixed | Thirst → 100 |
| `eat` | fixed | Hunger += food_value |
| `gather` | fixed | Inventory.berries += N |
| `build` | fixed (consumes resources) | Creates structure in world |
| `talk` | fixed (target agent) | Social relationship update |
| `attack` | fixed (target agent) | Damage target.health |
| `rest` | fixed | Energy → 100 |

### 2.4 Simulation Metrics (per-tick)

```python
@dataclass
class SimulationMetrics:
    population: int
    avg_hunger: float
    avg_thirst: float
    avg_health: float
    avg_energy: float
    total_wood: int
    total_food: int
    total_stone: int
    total_buildings: int
    deaths_this_tick: int
    births_this_tick: int
    tick_rate: float                # Actual ticks/second
```

### 2.5 Events (UI notifications & logs)

```python
@dataclass
class SimEvent:
    event_id: str                    # Unique ID (for dedup)
    type: SimEventType
    severity: Literal["info", "warning", "critical"]
    description: str                 # "Zog encountered Mila and shared berries"
    agent_ids: list[str]             # Agents involved
    position: tuple[float, float] | None  # Where it happened
    tick: int

type SimEventType = (
    "encounter" | "death" | "birth" | "build" | "fight" 
    | "discovery" | "llm_decision" | "resource_depleted"
    | "structure_completed" | "relationship_change"
)
```

---

## 3. LLM Orchestrator Contract

### 3.1 Prompt Template (injected context)

The orchestrator builds a prompt with:

1. **System prompt** (agent personality — user-defined)
2. **Current state** (hunger, thirst, position, inventory, nearby objects)
3. **Recent memories** (from ChromaDB — top 3-5 relevant)
4. **Relationships** (agents nearby, opinion scores)
5. **Trigger event** (why the LLM was called)

The LLM returns **only valid JSON** matching the `LLMPlan` schema above.

### 3.2 Trigger Conditions

| Event | Trigger Condition | Priority |
|-------|------------------|----------|
| `plan_completed` | Agent finished all steps of current plan | Medium |
| `critical_need` | Hunger < 15% or Thirst < 15% | HIGH |
| `encounter` | Another agent enters interaction radius | Low (filtered by sociability) |
| `attack` | Agent takes damage or witnesses an attack | HIGH |
| `discovery` | Agent finds unknown resource/structure | Low |
| `external_stimulus` | Player issues command or changes rules | HIGH |
| `idle_timeout` | Agent has been idle > 30 seconds | Medium |

---

## 4. SQLite Schema

```sql
-- Simulation events (for replay and analysis)
CREATE TABLE sim_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tick INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    description TEXT NOT NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Per-tick metrics (for historical charts)
CREATE TABLE tick_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tick INTEGER NOT NULL UNIQUE,
    population INTEGER NOT NULL,
    avg_hunger REAL NOT NULL,
    avg_thirst REAL NOT NULL,
    avg_health REAL NOT NULL,
    avg_energy REAL NOT NULL,
    total_wood INTEGER DEFAULT 0,
    total_food INTEGER DEFAULT 0,
    total_stone INTEGER DEFAULT 0,
    total_buildings INTEGER DEFAULT 0,
    deaths_this_tick INTEGER DEFAULT 0,
    births_this_tick INTEGER DEFAULT 0
);

-- World configurations (cached, source of truth is git)
CREATE TABLE world_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    config JSON NOT NULL,
    active BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent memory references (links to ChromaDB vectors)
CREATE TABLE agent_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    chroma_id TEXT NOT NULL UNIQUE,
    timestamp INTEGER NOT NULL,
    memory_type TEXT NOT NULL,   -- "experience" | "relationship" | "location"
    summary TEXT NOT NULL
);
```

---

## 5. Error Handling

```python
@dataclass
class ErrorPayload:
    code: str                      # "llm_timeout" | "invalid_plan" | "agent_not_found"
    message: str                   # Human-readable description
    details: dict | None           # Additional context
```

| Error Code | Cause | Recovery |
|------------|-------|----------|
| `llm_timeout` | LLM took > 30s to respond | Agent uses instinct (find food/water) |
| `llm_invalid_plan` | LLM returned malformed JSON | Retry once, then instinct fallback |
| `invalid_command` | Unknown command from client | Ignore, log warning |
| `agent_not_found` | Reference to non-existent agent | Skip operation |
