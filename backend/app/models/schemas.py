from pydantic import BaseModel
from typing import Literal


# --- Agent State ---
class AgentState(BaseModel):
    id: str
    name: str
    position: tuple[float, float]
    role: str
    hunger: float
    thirst: float
    energy: float
    health: float
    current_state: str = "idle"
    current_action: str | None = None
    current_action_emoji: str = ""
    action_progress: float = 0.0
    inventory: dict[str, int] = {}
    last_thought: str = ""


# --- Simulation Metrics ---
class SimulationMetrics(BaseModel):
    population: int = 0
    avg_hunger: float = 0
    avg_thirst: float = 0
    avg_health: float = 0
    avg_energy: float = 0


# --- Events ---
class SimEvent(BaseModel):
    event_id: str
    type: str
    severity: Literal["info", "warning", "critical"] = "info"
    description: str
    tick: int


# --- Tile Update ---
class TileUpdate(BaseModel):
    x: int
    y: int
    resource_type: str | None = None
    amount: int = 0


# --- Server Message ---
class ServerMessage(BaseModel):
    type: Literal["snapshot", "llm_response", "error", "config_ack"]
    payload: dict


# --- Client Message ---
class ClientMessage(BaseModel):
    type: Literal["command", "config_change", "agent_edit"]
    payload: dict


# --- World Snapshot ---
class WorldSnapshot(BaseModel):
    tick: int
    timestamp: float
    tiles: list[TileUpdate] = []
    agents: dict[str, AgentState] = {}
    removed_agents: list[str] = []
    metrics: SimulationMetrics = SimulationMetrics()
    events: list[SimEvent] = []
