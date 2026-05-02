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
    role_data: dict = field(default_factory=dict)

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

    # Dialogue bubbles
    current_dialogue: str | None = None
    dialogue_type: str | None = None  # "speech" | "thought"

    # Equipment
    equipment: dict[str, str] = field(
        default_factory=lambda: {"weapon": "fist", "armor": "none", "tool": "none"}
    )
    is_guarding: bool = False

    # Combat tracking
    _combat_attacker_id: str | None = None

    # Storage capacity bonus tracking
    _storage_nearby: bool = False

    # Exploration tracking
    explored_tiles: set[tuple[int, int]] = field(default_factory=set)


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
        from app.simulation.roles import apply_role_stats

        attrs = config.get("attributes", {})
        equipment = config.get("equipment", {"weapon": "fist", "armor": "none", "tool": "none"})
        agent = Agent(
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
            equipment=equipment,
        )
        apply_role_stats(agent)
        return agent

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

    def build_prompt(self, agent: Agent, world=None, agents=None) -> str:
        """Build a mock prompt string from agent state."""
        from app.simulation.actions import ActionResult
        lar = agent.last_action_result
        lar_str = "None (first tick)"
        if isinstance(lar, ActionResult):
            lar_str = f"{lar.action_type} success={lar.success} {lar.action_summary}"
        # Check conversation queue
        queue_info = ""
        if agent.conversation_queue:
            dialogue_msgs = [m for m in agent.conversation_queue if m.content.get("type") == "dialogue"]
            if dialogue_msgs:
                latest = dialogue_msgs[-1]
                text = latest.content.get("text", "")
                sender = latest.content.get("sender_name", latest.sender_id)
                sender_id = latest.sender_id
                queue_info = f' | Unread message from {sender} (id={sender_id}): "{text}"'
        return (
            f"Mock prompt for {agent.name}: "
            f"hunger={agent.hunger:.0f}, thirst={agent.thirst:.0f} "
            f"last_action={lar_str}{queue_info}"
        )

    def call_async(self, agent_id: str, prompt: str) -> asyncio.Future:
        """Create a future that will resolve with a varied mock plan after a delay."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[agent_id] = future

        # Extract agent name from prompt for varied responses
        agent_name = agent_id
        if "Mock prompt for " in prompt:
            agent_name = prompt.split("Mock prompt for ", 1)[1].split(":", 1)[0].strip()

        async def _resolve() -> None:
            await asyncio.sleep(random.uniform(*self.delay_range))
            if random.random() < self.success_rate:
                # ── Check for unread messages and respond to sender ──
                say_to = None
                if "Unread message from" in prompt:
                    # Extract sender info: "Unread message from {name} (id={sender_id}): \"{text}\""
                    after = prompt.split("Unread message from ", 1)[1]
                    parts = after.split(":", 1)
                    sender_part = parts[0].strip()
                    # sender_part looks like: Alice (id=a2) or just a2 if no sender_name
                    if "(id=" in sender_part:
                        sender_id = sender_part.split("(id=", 1)[1].rstrip(")")
                    else:
                        sender_id = sender_part
                    # Always respond when there's an unread message (deterministic for tests)
                    responses_to_stranger = [
                        "Oh, hello there!",
                        "Nice to meet you!",
                        "Thanks for reaching out.",
                        "I appreciate you talking to me.",
                    ]
                    responses_to_friend = [
                        "Hey! Good to hear from you!",
                        "I was just thinking about that too!",
                        "Great! Let's work together on this.",
                        "Absolutely, I agree!",
                    ]
                    # Default to stranger responses (we don't have relationship info in mock)
                    say_text = random.choice(responses_to_stranger + responses_to_friend)
                    say_to = {"agent_id": sender_id, "text": say_text}

                # ── Varied say_to (50% chance) when no unread messages ──
                if say_to is None and "Unread message from" not in prompt:
                    if random.random() < 0.5:
                        targets = [t for t in ("agent_001", "agent_002", "agent_003") if t != agent_id]
                        if targets:
                            target_id = random.choice(targets)
                            say_texts = [
                                "Hey, how are things going?",
                                "I found some good spots nearby!",
                                "We should stick together out here.",
                                "Have you seen any resources around?",
                                "Stay safe out there, alright?",
                                "The world is full of opportunities!",
                                "I'll cover this side, you check over there.",
                                "Let me know if you need a hand.",
                                "There's plenty to gather today!",
                                "Watch your step in unknown areas.",
                            ]
                            say_to = {"agent_id": target_id, "text": random.choice(say_texts)}

                # ── Varied think_aloud ──
                thoughts = [
                    "I should explore the area and gather what I can.",
                    "This place looks promising. Time to get to work.",
                    "I wonder what's over that hill...",
                    "Need to find more food and water for the tribe.",
                    "The tribe needs resources. Let me focus.",
                    "I should check on my fellow tribe members.",
                    "There's always more to discover out there.",
                    "Let me be efficient with my time today.",
                    "The land provides, but we must work for it.",
                    "Every resource counts. Let's not waste any.",
                    "I feel like today is going to be productive.",
                    "Better keep moving — there's work to be done.",
                    "I should find a good spot to gather supplies.",
                ]

                # ── Varied intentions ──
                intentions = [
                    "Survive and gather resources",
                    "Explore the unknown territories",
                    "Secure food and water for the tribe",
                    "Find better resources for crafting",
                    "Scout the area for opportunities",
                ]

                # ── Varied steps ──
                step_action = random.choice(["gather", "explore", "move"])
                steps = [
                    {
                        "action": "move",
                        "target": [random.randint(5, 45), random.randint(5, 45)],
                        "duration_secs": random.randint(3, 8),
                        "reason": "Scouting the area",
                    },
                    {
                        "action": step_action,
                        "target": None,
                        "duration_secs": random.randint(5, 12),
                        "reason": "Working for the tribe",
                    },
                ]

                future.set_result(
                    {
                        "success": True,
                        "data": {
                            "reasoning": f"{agent_name} is assessing the situation and planning next moves.",
                            "intention": random.choice(intentions),
                            "priority": "medium",
                            "steps": steps,
                            "abort_if": {
                                "hunger < 15": "Find and eat berries",
                                "thirst < 15": "Find water",
                            },
                            "think_aloud": random.choice(thoughts),
                            "say_to": say_to,
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
