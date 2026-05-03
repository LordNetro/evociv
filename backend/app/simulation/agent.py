"""Agent entity, FSM, factory, and mock LLM orchestrator."""

from __future__ import annotations

import asyncio
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.definitions import DEFINITIONS


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

    # Skill progression
    skills: dict[str, int] = field(default_factory=dict)

    # Status effects
    active_effects: dict[str, dict] = field(default_factory=dict)

    # Emotions (float intensity model)
    emotions: dict[str, dict] = field(default_factory=dict)

    # Map memory (tile vision tracking)
    tile_memory: dict = field(default_factory=dict)

    # Director mode: injected thoughts (consumed by LLM pipeline)
    injected_thoughts: list[str] = field(default_factory=list)


class FSM:
    """Simple state machine for agent behaviour."""

    VALID_TRANSITIONS = {
        "idle": {"evaluate"},
        "evaluate": {"idle", "moving", "executing", "llm_trigger"},
        "moving": {"executing", "evaluate"},
        "executing": {"moving", "evaluate"},
        "llm_trigger": {"llm_waiting", "evaluate"},  # evaluate added for F3 cooldown guard
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
        inventory = config.get("inventory", {})
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
            inventory=inventory,
        )
        apply_role_stats(agent)
        return agent

    @staticmethod
    def create_default_agents() -> list[Agent]:
        """Create default agents from DEFINITIONS.agent_defaults."""
        agents: list[Agent] = []
        for i, default in enumerate(DEFINITIONS.agent_defaults.agents):
            agent = Agent(
                id=f"agent_{i + 1:03d}",
                name=default.name,
                position=tuple(default.position),
                role=default.role,
                strength=default.strength,
                intelligence=default.intelligence,
                sociability=default.sociability,
                speed=default.speed,
                sex=default.sex,
                age=default.age,
                max_age=default.max_age,
                equipment=dict(default.equipment),
            )
            agents.append(agent)
        return agents

    @staticmethod
    def from_world_config(world_config: dict[str, Any]) -> list[Agent]:
        """Create agents from a world config dict (already parsed)."""
        agents: list[Agent] = []
        for agent_cfg in world_config.get("agents", []):
            agents.append(AgentFactory.from_config(agent_cfg))
        return agents


class MockLLMOrchestrator:
    """Generates varied, role-aware JSON plans for development / testing.

    Each agent receives plans that reflect their role, current needs,
    inventory, and social context — making the simulation feel alive
    without requiring a real LLM API key.
    """

    # Role → weighted actions for plan generation
    ROLE_ACTIONS: dict[str, list[str]] = {
        "gatherer": ["gather", "explore", "chop", "socialize", "gather", "gather"],
        "builder":  ["gather", "chop", "build", "build", "gather", "explore"],
        "scout":    ["explore", "move", "explore", "gather", "explore", "socialize"],
        "hunter":   ["hunt", "gather", "explore", "hunt", "socialize"],
        "fisher":   ["fish", "gather", "explore", "fish", "socialize"],
        "farmer":   ["farm", "gather", "build", "farm", "explore"],
        "miner":    ["mine", "gather", "mine", "chop", "explore"],
        "crafter":  ["gather", "craft", "craft", "chop", "socialize"],
        "fighter":  ["guard", "explore", "attack", "gather"],
        "healer":   ["heal", "gather", "explore", "socialize", "gather"],
    }

    DEFAULT_ACTIONS = ["gather", "explore", "move"]

    # Crafting recipes the LLM knows about (tier 1)
    KNOWN_RECIPES = ["stone_axe", "stone_pickaxe", "spear", "fishing_rod",
                      "hoe", "fiber_armor", "planks", "stone_blade", "rope"]
    BUILD_TYPES = ["workbench_structure", "house", "storage_hut", "wall", "farm"]

    def __init__(
        self,
        delay_range: tuple[float, float] = (0.5, 2.0),
        success_rate: float = 0.9,
    ):
        self.delay_range = delay_range
        self.success_rate = success_rate
        self._pending: dict[str, asyncio.Future] = {}
        self._pending_tasks: dict[str, asyncio.Task] = {}

    def _extract_agent_info(self, prompt: str) -> tuple[str, float, float, str]:
        """Extract agent name, hunger, thirst, and role from the prompt string."""
        name = "Unknown"
        hunger = 50.0
        thirst = 50.0
        role = "gatherer"
        if "Mock prompt for " in prompt:
            name = prompt.split("Mock prompt for ", 1)[1].split(":", 1)[0].strip()
        if "hunger=" in prompt:
            try:
                hunger = float(prompt.split("hunger=", 1)[1].split(",")[0].strip())
            except (ValueError, IndexError):
                pass
        if "thirst=" in prompt:
            try:
                thirst = float(prompt.split("thirst=", 1)[1].split(",")[0].strip())
            except (ValueError, IndexError):
                pass
        # Role is not in prompt currently — we use agent_id to determine
        # In a real impl we'd add role to the prompt, but for now infer from id/name
        return name, hunger, thirst, role

    def _get_role_for_agent(self, agent_id: str) -> str:
        """Determine agent's role from their id (since role isn't in prompt yet)."""
        # This is a mapping of known agent IDs to roles
        # In production, the prompt would include the agent's role
        role_map = {
            "agent_001": "gatherer",  # Zog
            "agent_002": "builder",   # Mila
            "agent_003": "scout",     # Kael
            "agent_004": "miner",     # Nyx
        }
        # For unknown agents, assign based on name if possible, or random
        return role_map.get(agent_id, random.choice(list(self.ROLE_ACTIONS.keys())))

    def _generate_craft_action(self) -> dict:
        """Generate a craft action for a random known recipe."""
        recipe = random.choice(self.KNOWN_RECIPES)
        return {
            "action": "craft",
            "recipe": recipe,
            "duration_secs": random.randint(8, 20),
            "reason": f"Crafting {recipe.replace('_', ' ')} for the tribe",
        }

    def _generate_build_action(self) -> dict:
        """Generate a build action for a random structure."""
        build_type = random.choice(self.BUILD_TYPES)
        return {
            "action": "build",
            "structure_type": build_type,
            "duration_secs": random.randint(10, 25),
            "reason": f"Building a {build_type.replace('_', ' ')} for the settlement",
        }

    def _generate_socialize_action(self, agent_id: str) -> dict | None:
        """Generate a socialize action toward a random other agent."""
        other_ids = [f"agent_{i:03d}" for i in range(1, 5) if f"agent_{i:03d}" != agent_id]
        if other_ids:
            partner = random.choice(other_ids)
            return {
                "action": "socialize",
                "partner_id": partner,
                "target": None,
                "duration_secs": random.randint(5, 15),
                "reason": "Building bonds with the community",
            }
        return None

    def _generate_role_step(self, action: str, agent_id: str) -> dict:
        """Generate a plan step for a given action type."""
        if action == "craft":
            return self._generate_craft_action()
        elif action == "build":
            return self._generate_build_action()
        elif action == "socialize":
            soc = self._generate_socialize_action(agent_id)
            if soc:
                return soc
            # Fallback to gather
            return self._generate_role_step("gather", agent_id)
        elif action == "hunt":
            return {
                "action": "hunt", "target": None,
                "duration_secs": random.randint(10, 20),
                "reason": "Hunting for food and materials",
            }
        elif action == "fish":
            return {
                "action": "fish", "target": None,
                "duration_secs": random.randint(8, 15),
                "reason": "Fishing for food",
            }
        elif action == "farm":
            return {
                "action": "farm", "target": None,
                "duration_secs": random.randint(10, 18),
                "reason": "Tending the farm for long-term food",
            }
        elif action == "mine":
            return {
                "action": "mine", "target": None,
                "duration_secs": random.randint(10, 18),
                "reason": "Mining for stone and ore",
            }
        elif action == "chop":
            return {
                "action": "chop", "target": None,
                "duration_secs": random.randint(8, 15),
                "reason": "Chopping wood for the tribe",
            }
        elif action == "guard":
            return {
                "action": "guard", "target": None,
                "duration_secs": random.randint(10, 20),
                "reason": "Standing guard to protect the settlement",
            }
        elif action == "explore":
            return {
                "action": "explore", "target": None,
                "duration_secs": random.randint(8, 15),
                "reason": "Exploring unknown areas for resources",
            }
        elif action == "heal":
            return {
                "action": "heal", "target": None,
                "duration_secs": random.randint(6, 12),
                "reason": "Healing and tending to the injured",
            }
        else:  # gather, move, and default
            return {
                "action": "gather", "target": None,
                "duration_secs": random.randint(5, 12),
                "reason": "Gathering resources for the tribe",
            }

    def _generate_plan_steps(self, agent_id: str, role: str) -> list[dict]:
        """Generate a multi-step plan appropriate for the agent's role."""
        # Get weighted actions for this role
        actions = self.ROLE_ACTIONS.get(role, self.DEFAULT_ACTIONS)

        steps: list[dict] = []

        # Step 1: usually move to a useful position
        steps.append({
            "action": "move",
            "target": [random.randint(5, 45), random.randint(5, 45)],
            "duration_secs": random.randint(3, 8),
            "reason": "Moving to a productive area",
        })

        # Steps 2-4: role-appropriate actions
        num_work_steps = random.randint(2, 3)
        for _ in range(num_work_steps):
            chosen = random.choice(actions)
            steps.append(self._generate_role_step(chosen, agent_id))

        # Occasionally add a socialize step
        if random.random() < 0.3:
            soc = self._generate_socialize_action(agent_id)
            if soc:
                steps.append(soc)

        return steps

    def build_prompt(self, agent: Agent, world=None, agents=None) -> str:
        """Build a mock prompt string from agent state."""
        from app.simulation.actions import ActionResult
        lar = agent.last_action_result
        lar_str = "None (first tick)"
        if isinstance(lar, ActionResult):
            lar_str = f"{lar.action_type} success={lar.success} {lar.action_summary}"
        queue_info = ""
        if agent.conversation_queue:
            # Check for both dialogue AND greeting messages
            unread_msgs = [
                m for m in agent.conversation_queue
                if m.content.get("type") in ("dialogue", "greeting")
            ]
            if unread_msgs:
                latest = unread_msgs[-1]
                msg_type = latest.content.get("type", "message")
                text = latest.content.get("text") or latest.content.get("sender_name", "")
                sender = latest.content.get("sender_name", latest.sender_id)
                sender_id = latest.sender_id
                queue_info = f' | Unread {msg_type} from {sender} (id={sender_id}): "{text}"'
        prompt = (
            f"Mock prompt for {agent.name}: "
            f"hunger={agent.hunger:.0f}, thirst={agent.thirst:.0f} "
            f"role={agent.role} "
            f"last_action={lar_str}{queue_info}"
        )

        # Inject thoughts: "A voice in your head says: ..."
        for thought in agent.injected_thoughts:
            prompt = f"A voice in your head says: {thought}\n\n{prompt}"
        agent.monologue_history.extend(agent.injected_thoughts)
        agent.injected_thoughts.clear()

        return prompt

    def call_async(self, agent_id: str, prompt: str) -> asyncio.Future:
        """Create a future that will resolve with a varied role-aware plan."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[agent_id] = future

        agent_name, hunger, thirst, _ = self._extract_agent_info(prompt)
        role = self._get_role_for_agent(agent_id)

        # Also extract role from prompt if available
        if "role=" in prompt:
            try:
                role_part = prompt.split("role=", 1)[1].split(" ")[0].strip()
                if role_part:
                    role = role_part
            except (ValueError, IndexError):
                pass

        async def _resolve() -> None:
            await asyncio.sleep(random.uniform(*self.delay_range))
            if random.random() < self.success_rate:
                # ── Dialogue: respond to incoming messages ──
                say_to = None
                if "Unread " in prompt and "(id=" in prompt:
                    after = prompt.split("(id=", 1)[1]
                    sender_id = after.split(")", 1)[0].strip()
                    # Pick a context-aware response
                    if "greeting" in prompt:
                        responses = [
                            "Hello there! Good to meet you!",
                            "Hey! How are things going?",
                            "Nice to see you!",
                            "Greetings! Glad we crossed paths.",
                        ]
                    else:
                        responses = [
                            "Oh, hello there!", "Nice to meet you!",
                            "Thanks for reaching out.", "Hey! Good to hear from you!",
                            "I was just thinking about that too!",
                            "Great! Let's work together on this.",
                        ]
                    say_to = {"agent_id": sender_id, "text": random.choice(responses)}

                # ── Proactive dialogue (20% chance) ──
                if say_to is None and random.random() < 0.2:
                    other_ids = [f"agent_{i:03d}" for i in range(1, 5) if f"agent_{i:03d}" != agent_id]
                    if other_ids:
                        target = random.choice(other_ids)
                        say_texts = [
                            "Hey, how are things going?",
                            "I found some good spots nearby!",
                            "We should stick together out here.",
                            "Have you seen any resources around?",
                            "Let me know if you need a hand.",
                            "There's plenty to gather today!",
                            "The tribe is growing strong!",
                            "I'll cover this side, you check over there.",
                        ]
                        say_to = {"agent_id": target, "text": random.choice(say_texts)}

                # ── Generate role-aware plan ──
                steps = self._generate_plan_steps(agent_id, role)

                role_intentions = {
                    "gatherer": "Secure food and resources for the tribe",
                    "builder": "Construct and improve the settlement",
                    "scout": "Explore and map unknown territories",
                    "hunter": "Hunt for food and materials",
                    "fisher": "Fish to feed the community",
                    "farmer": "Establish and tend to farms",
                    "miner": "Mine for stone and precious ores",
                    "crafter": "Craft tools and equipment for the tribe",
                    "fighter": "Protect the settlement from threats",
                    "healer": "Heal and care for the community",
                }
                intention = role_intentions.get(role, "Contribute to the tribe's survival")

                role_thoughts = {
                    "gatherer": [
                        "I should gather as many resources as I can.",
                        "The tribe needs food and materials.",
                    ],
                    "builder": [
                        "I need to build more structures for the settlement.",
                        "A good foundation is key to a strong tribe.",
                    ],
                    "scout": [
                        "There's still so much to explore out there.",
                        "Knowledge of the land is power.",
                    ],
                }
                thoughts = role_thoughts.get(role, [
                    "I should focus on my role and help the tribe.",
                    "Every contribution matters for the community.",
                ])

                if not future.done():
                    future.set_result({
                        "success": True,
                        "data": {
                            "reasoning": f"{agent_name} ({role}) is planning next actions.",
                            "intention": intention,
                            "priority": "medium",
                            "steps": steps,
                            "abort_if": {
                                "hunger < 15": "Find and eat berries",
                                "thirst < 15": "Find water",
                            },
                            "think_aloud": random.choice(thoughts),
                            "say_to": say_to,
                        },
                    })
            else:
                if not future.done():
                    future.set_result({"success": False, "error": "Simulated LLM failure"})

        task = asyncio.create_task(_resolve())
        self._pending_tasks[agent_id] = task
        return future

    def cancel_agent_task(self, agent_id: str) -> None:
        """Cancel the background task for a pending LLM call and remove from tracking."""
        task = self._pending_tasks.pop(agent_id, None)
        if task and not task.done():
            task.cancel()

    def poll_completed(self) -> list[tuple[str, dict]]:
        """Return all completed futures as (agent_id, response) tuples."""
        completed: list[tuple[str, dict]] = []
        for agent_id, future in list(self._pending.items()):
            if future.done():
                try:
                    result = future.result()
                    completed.append((agent_id, result))
                except Exception:
                    # Future was cancelled (e.g., by director mode command)
                    pass
                del self._pending[agent_id]
                self._pending_tasks.pop(agent_id, None)
        return completed


__all__ = [
    "Agent",
    "RelationshipData",
    "FSM",
    "AgentFactory",
    "MockLLMOrchestrator",
]
