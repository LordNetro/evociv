"""Agent entity, FSM, factory, and mock LLM orchestrator."""

from __future__ import annotations

import asyncio
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class RelationshipData:
    """Tracks relationship between two agents."""
    interaction_count: int = 0
    last_interaction_tick: int = 0
    score: float = 0.0  # -1.0 to 1.0


@dataclass
class Agent:
    """Simulation agent with physical state, attributes, FSM, and plan tracking."""

    id: str  # e.g. "agent_001"
    name: str  # e.g. "Zog"
    position: tuple[float, float]  # (x, y) float coords for smooth movement

    # Physical state (0-100)
    hunger: float = 50.0
    thirst: float = 50.0
    energy: float = 100.0
    health: float = 100.0

    # Attributes (0-100)
    strength: int = 50
    intelligence: int = 50
    sociability: int = 50
    speed: int = 50

    # Age & reproduction
    age: int = 0
    max_age: int = 3000  # default, overridden in factory
    sex: str = "male"  # "male" or "female"

    # Role
    role: str = "gatherer"

    # FSM
    fsm_state: str = "idle"

    # Action progress
    action_progress: float = 0.0
    action_duration: int = 0  # ticks remaining for current action
    current_action: Optional[str] = None
    current_action_emoji: str = ""

    # Movement
    move_path: list = field(default_factory=list)
    move_progress: float = 0.0
    target_position: Optional[tuple[float, float]] = None

    # Plan
    active_plan: Optional[dict] = None
    plan_step_index: int = 0

    # Inventory
    inventory: dict[str, int] = field(default_factory=dict)

    # LLM
    llm_call_pending: bool = False
    llm_future: Optional[asyncio.Future] = None  # noqa: F821

    # Consciousness
    last_thought: str = ""
    system_prompt: str = ""
    monologue_history: list = field(default_factory=list)

    # Social features
    last_action_result: Optional[Any] = None  # ActionResult from last tick
    relationships: dict[str, RelationshipData] = field(default_factory=dict)
    knowledge: dict[str, dict[str, Any]] = field(default_factory=dict)
    conversation_queue: list = field(default_factory=list)
    is_child: bool = False
    parent_id: Optional[str] = None
    maturity_age: int = 500
    faction_id: Optional[str] = None


class FSM:
    """Simple state machine for agent behaviour."""

    VALID_TRANSITIONS = {
        "idle": {"evaluate"},
        "evaluate": {"idle", "moving", "executing", "llm_trigger"},
        "moving": {"executing", "evaluate"},
        "executing": {"moving", "evaluate"},
        "llm_trigger": {"llm_waiting"},
        "llm_waiting": {"moving", "evaluate", "executing"},
    }

    def __init__(self) -> None:
        self.current_state = "idle"

    def transition_to(self, new_state: str) -> None:
        """Transition to *new_state* if it is valid from the current state."""
        if new_state not in self.VALID_TRANSITIONS.get(self.current_state, set()):
            raise ValueError(
                f"Invalid transition: {self.current_state} → {new_state}"
            )
        self.current_state = new_state


class AgentFactory:
    """Factory for creating :class:`Agent` instances."""

    @staticmethod
    def from_config(config: dict[str, Any]) -> Agent:
        """Create a single agent from a config dict."""
        attrs = config.get("attributes", {})
        return Agent(
            id=config.get("id", f"agent_{uuid.uuid4().hex[:6]}"),
            name=config["name"],
            position=tuple(config.get("position", [0.0, 0.0])),  # type: ignore[arg-type]
            role=config.get("role", "gatherer"),
            strength=attrs.get("strength", 50),
            intelligence=attrs.get("intelligence", 50),
            sociability=attrs.get("sociability", 50),
            speed=attrs.get("speed", 50),
            sex=attrs.get("sex", "male"),
            age=attrs.get("age", 0),
            max_age=attrs.get("max_age", 3000),
        )

    @staticmethod
    def create_default_agents() -> list[Agent]:
        """Create the 3 default agents: Zog, Mila, Kael."""
        return [
            Agent(
                id="agent_001",
                name="Zog",
                position=(5.0, 5.0),
                role="gatherer",
                strength=60,
                intelligence=40,
                sociability=50,
                speed=55,
                sex="male",
                age=0,
                max_age=3500,
            ),
            Agent(
                id="agent_002",
                name="Mila",
                position=(35.0, 30.0),
                role="builder",
                strength=70,
                intelligence=55,
                sociability=40,
                speed=35,
                sex="female",
                age=0,
                max_age=4000,
            ),
            Agent(
                id="agent_003",
                name="Kael",
                position=(45.0, 10.0),
                role="scout",
                strength=45,
                intelligence=60,
                sociability=65,
                speed=80,
                sex="male",
                age=0,
                max_age=3000,
            ),
        ]

    @staticmethod
    def from_world_config(world_config: dict[str, Any]) -> list[Agent]:
        """Create agents from a world config dict (already parsed)."""
        agents: list[Agent] = []
        for agent_cfg in world_config.get("agents", []):
            agents.append(AgentFactory.from_config(agent_cfg))
        return agents


class MockLLMOrchestrator:
    """Returns hardcoded JSON plans for development / testing."""

    def __init__(
        self,
        delay_range: tuple[float, float] = (0.5, 2.0),
        success_rate: float = 0.9,
    ):
        self.delay_range = delay_range
        self.success_rate = success_rate
        self._pending: dict[str, asyncio.Future] = {}

    def build_prompt(self, agent: Agent, world=None) -> str:
        """Build a mock prompt string from agent state."""
        from app.simulation.actions import ActionResult
        lar = agent.last_action_result
        lar_str = "None (first tick)"
        if isinstance(lar, ActionResult):
            lar_str = f"{lar.action_type} success={lar.success} {lar.action_summary}"
        return (
            f"Mock prompt for {agent.name}: "
            f"hunger={agent.hunger:.0f}, thirst={agent.thirst:.0f} "
            f"last_action={lar_str}"
        )

    def call_async(self, agent_id: str, prompt: str) -> asyncio.Future:
        """Create a future that will resolve with a mock plan after a delay."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[agent_id] = future

        async def _resolve() -> None:
            await asyncio.sleep(random.uniform(*self.delay_range))
            if random.random() < self.success_rate:
                future.set_result(
                    {
                        "success": True,
                        "data": {
                            "reasoning": f"Mock reasoning for {agent_id}",
                            "intention": "Survive and gather resources",
                            "priority": "medium",
                            "steps": [
                                {
                                    "action": "move",
                                    "target": [25, 25],
                                    "duration_secs": 5,
                                    "reason": "Exploring",
                                },
                                {
                                    "action": "gather",
                                    "target": None,
                                    "duration_secs": 8,
                                    "reason": "Collect resources",
                                },
                            ],
                            "abort_if": {
                                "hunger < 15": "Find and eat berries",
                                "thirst < 15": "Find water",
                            },
                            "think_aloud": (
                                "I should explore the area and gather what I can."
                            ),
                        },
                    }
                )
            else:
                future.set_result({"success": False, "error": "Simulated LLM failure"})

        asyncio.create_task(_resolve())
        return future

    def poll_completed(self) -> list[tuple[str, dict]]:
        """Return all completed futures as (agent_id, response) tuples."""
        completed: list[tuple[str, dict]] = []
        for agent_id, future in list(self._pending.items()):
            if future.done():
                completed.append((agent_id, future.result()))
                del self._pending[agent_id]
        return completed


__all__ = [
    "Agent",
    "RelationshipData",
    "FSM",
    "AgentFactory",
    "MockLLMOrchestrator",
]
