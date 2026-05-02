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
    sex: str = "male"
    age: int = 0
    max_age: int = 3000
    strength: int = 50
    intelligence: int = 50
    sociability: int = 50
    speed: int = 50
    system_prompt: str = ""
    monologue_history: list[str] = []
    relationships: dict[str, dict] = {}
    knowledge: dict[str, dict] = {}
    is_child: bool = False
    parent_id: str | None = None
    faction_id: str | None = None
    current_dialogue: str | None = None
    dialogue_type: str | None = None
    equipment: dict[str, str] = {}
    skills: dict[str, int] = {}
    active_effects: dict[str, dict] = {}
    emotions: dict[str, dict] = {}


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
    subtype: str | None = None


# --- Server Message ---
class ServerMessage(BaseModel):
    type: Literal["snapshot", "llm_response", "error", "config_ack"]
    payload: dict


# --- Client Message ---
class ClientMessage(BaseModel):
    type: Literal["command", "config_change", "agent_edit"]
    payload: dict


# --- Structure Update ---
class StructureUpdate(BaseModel):
    id: str
    structure_type: str
    position: tuple[int, int]
    health: float
    max_health: float
    owner_id: str | None = None


# --- World Snapshot ---
class WorldSnapshot(BaseModel):
    tick: int
    timestamp: float
    tiles: list[TileUpdate] = []
    agents: dict[str, AgentState] = {}
    removed_agents: list[str] = []
    metrics: SimulationMetrics = SimulationMetrics()
    events: list[SimEvent] = []
    factions: list[dict] = []
    colony_stats: dict | None = None
    structures: list[StructureUpdate] = []
    time_state: dict = {}
    weather_state: dict = {}
    faction_tile_visibility: dict[str, dict[str, list[dict]]] = {}
