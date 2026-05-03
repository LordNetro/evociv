"""Real LLM orchestrator calling Ollama directly via HTTP (more reliable than LiteLLM for local models)."""

import asyncio
import json
import logging
import time
from typing import Optional

import httpx

from app.core.config import settings
from app.simulation.agent import Agent, MockLLMOrchestrator
from app.ai.prompts import build_agent_prompt
from app.ai.memory import AgentMemory

logger = logging.getLogger("evociv.llm")
logger.setLevel(logging.INFO)


class RealLLMOrchestrator:
    """Orchestrates LLM calls via direct Ollama HTTP API.

    Falls back to MockLLMOrchestrator if the real LLM is unavailable and
    settings.llm_fallback_to_mock is True.
    """

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        timeout: int = 30,
        memory: Optional[AgentMemory] = None,
        faction_manager=None,
    ):
        self.model = model
        self.api_url = f"{base_url.rstrip('/')}/api/chat"
        self.timeout = timeout
        self.memory = memory or AgentMemory()
        self.faction_manager = faction_manager
        self._pending: dict[str, asyncio.Future] = {}
        self._mock = MockLLMOrchestrator()

        # Track whether the real LLM connection works
        self._real_available: Optional[bool] = None
        self._last_test_time = 0
        self._test_interval = 60

        self._llm_semaphore: asyncio.Semaphore | None = None
        self._background_tasks: set[asyncio.Task] = set()
        self._pending_tasks: dict[str, asyncio.Task] = {}

    @property
    def is_available(self) -> Optional[bool]:
        """Public read-only: None=untested, True=up, False=down."""
        return self._real_available

    def build_prompt(self, agent: Agent, world=None, agents=None) -> str:
        """Build prompt with agent state, memories, and nearby info."""
        nearby_resources = "none"
        nearby_structures = ""
        if world:
            resources = world.get_nearby_resources(agent.position, radius=5)
            if resources:
                nearby_resources = "; ".join(
                    f"{r[2]} at ({r[0]},{r[1]}) amount={r[3]}" for r in resources[:5]
                )
            structures = world.structures.get_nearby_structures(
                (int(agent.position[0]), int(agent.position[1])), radius=5
            )
            if structures:
                nearby_structures = "; ".join(
                    f"{s.structure_type} at ({s.position[0]},{s.position[1]})"
                    for s in structures[:5]
                )
        memories = self.memory.format_recent(agent.id, n=5)
        trigger = agent.last_thought or "Time to decide what to do"
        # Resolve faction context if available
        faction_context = ""
        if agent.faction_id:
            faction = (
                self.faction_manager.get_faction(agent.faction_id)
                if getattr(self, "faction_manager", None) is not None
                else None
            )
            if faction:
                faction_context = f'- You are a member of "{faction.name}" (color: {faction.color})'
            else:
                faction_context = f'- You are a member of faction "{agent.faction_id}"'

        # Compute craftable recipes
        from app.ai.prompts import _get_craftable_recipes, _get_buildable_structures, _get_all_recipes
        craftable_recipes = _get_craftable_recipes(agent)
        all_recipes = _get_all_recipes(agent)
        buildable_structures = _get_buildable_structures(agent)

        # Format equipment
        equipment = (
            f"weapon: {agent.equipment.get('weapon', 'fist')}, "
            f"armor: {agent.equipment.get('armor', 'none')}, "
            f"tool: {agent.equipment.get('tool', 'none')}"
        )

        # Compute nearby hostiles
        nearby_hostiles = ""
        nearby_friendly = []
        if agents:
            import math
            hostiles: list[str] = []
            for other in agents:
                if other.id == agent.id:
                    continue
                dist = math.hypot(
                    agent.position[0] - other.position[0],
                    agent.position[1] - other.position[1],
                )
                if dist <= 5.0:
                    entry = f"{other.name} (id:{other.id}, {other.role}) at ({int(other.position[0])},{int(other.position[1])})"
                    # Hostile if different faction or no faction
                    if other.faction_id != agent.faction_id:
                        hostiles.append(entry)
                    # Friendly if same faction or no faction
                    if other.faction_id == agent.faction_id or not other.faction_id:
                        nearby_friendly.append(entry)
            nearby_hostiles = "; ".join(hostiles)
        nearby_agents_str = "; ".join(nearby_friendly) if nearby_friendly else "none"

        # Format relationship context
        rel_context = ""
        if agent.relationships:
            entries = []
            for other_id, rel in list(agent.relationships.items())[:5]:
                other = next((a for a in (agents or []) if a.id == other_id), None)
                name = other.name if other else other_id
                entries.append(f"{name} (id:{other_id}): score={rel.score:.2f}, chats={rel.interaction_count}")
            rel_context = "; ".join(entries)

        # Format weather and time context
        weather_str = "(unknown)"
        time_str = "(unknown)"
        if world and hasattr(world, 'weather') and hasattr(world, 'time'):
            w_def = world.weather._get_current_def()
            weather_str = f"{w_def.icon} {w_def.name}" if w_def else world.weather.current_weather
            t = world.time
            time_str = f"{t.time_of_day_label} (Day {t.day_count}, tick {t.tick_count_of_day}/{t.day_length_ticks})"

        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources=nearby_resources,
            nearby_agents=nearby_agents_str,
            memories=memories,
            trigger=trigger,
            last_action_result=agent.last_action_result,
            faction_context=faction_context,
            nearby_structures=nearby_structures,
            craftable_recipes=craftable_recipes,
            all_recipes=all_recipes,
            buildable_structures=buildable_structures,
            equipment=equipment,
            nearby_hostiles=nearby_hostiles,
            relationship_context=rel_context,
            weather=weather_str,
            time_str=time_str,
        )

        # Inject thoughts: "A voice in your head says: ..."
        for thought in agent.injected_thoughts:
            prompt = f"A voice in your head says: {thought}\n\n{prompt}"
        agent.monologue_history.extend(agent.injected_thoughts)
        agent.injected_thoughts.clear()

        return prompt

    async def check_availability(self) -> bool:
        """Test if Ollama is reachable via its /api/tags endpoint."""
        now = time.monotonic()
        if self._real_available is not None and now - self._last_test_time < self._test_interval:
            return self._real_available

        self._last_test_time = now
        try:
            base = settings.llm_base_url.rstrip("/")
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{base}/api/tags")
                self._real_available = resp.status_code == 200
                if self._real_available:
                    logger.info(f"Ollama available at {base}")
                else:
                    logger.warning(f"Ollama returned status {resp.status_code}")
        except Exception as e:
            self._real_available = False
            logger.warning(f"Ollama not reachable ({e})")
        return self._real_available

    def call_async(self, agent_id: str, prompt: str) -> asyncio.Future:
        """Call Ollama asynchronously. Returns a Future (same interface as Mock)."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[agent_id] = future

        async def _resolve() -> None:
            try:
                # Initialize semaphore lazily (avoids "no running loop" on import)
                if self._llm_semaphore is None:
                    self._llm_semaphore = asyncio.Semaphore(1)

                async with self._llm_semaphore:
                    if settings.llm_enabled:
                        available = await asyncio.wait_for(
                            self.check_availability(), timeout=10
                        )
                        if available:
                            total_timeout = self.timeout + 5
                            result = await asyncio.wait_for(
                                self._call_ollama(prompt),
                                timeout=total_timeout,
                            )
                        else:
                            raise RuntimeError("LLM disabled or unavailable")
                    else:
                        raise RuntimeError("LLM disabled or unavailable")

                if result.get("success"):
                    plan = result.get("data", {})
                    intention = plan.get("intention", "")
                    reasoning = plan.get("reasoning", "")
                    if intention:
                        self.memory.add_thought(agent_id, 0, f"Planned: {intention}. {reasoning}")
                if not future.done():
                    future.set_result(result)

            except asyncio.TimeoutError:
                logger.warning(f"Ollama _resolve timed out for {agent_id}")
                if settings.llm_fallback_to_mock:
                    logger.debug(f"Mock fallback for {agent_id}")
                    mock_future = self._mock.call_async(agent_id, prompt)
                    mock_result = await mock_future
                    if not future.done():
                        future.set_result(mock_result)
                else:
                    if not future.done():
                        future.set_result({"success": False, "error": "LLM call timed out"})

            except Exception as e:
                logger.warning(f"Ollama _resolve exception for {agent_id}: {type(e).__name__}: {e}")
                if settings.llm_fallback_to_mock:
                    logger.debug(f"Mock fallback for {agent_id}")
                    mock_future = self._mock.call_async(agent_id, prompt)
                    mock_result = await mock_future
                    if not future.done():
                        future.set_result(mock_result)
                else:
                    if not future.done():
                        future.set_result({"success": False, "error": str(e)})

        task = asyncio.create_task(_resolve())
        self._pending_tasks[agent_id] = task
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return future

    def cancel_agent_task(self, agent_id: str) -> None:
        """Cancel the background task for a pending LLM call and remove from tracking."""
        task = self._pending_tasks.pop(agent_id, None)
        if task and not task.done():
            task.cancel()

    async def _call_ollama(self, prompt: str) -> dict:
        """Call Ollama's /api/chat with JSON mode."""
        try:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.7,
                    "num_predict": 1024,
                },
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.api_url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            content = data.get("message", {}).get("content", "")
            plan = json.loads(content)

            return {
                "success": True,
                "data": {
                    "reasoning": plan.get("reasoning", ""),
                    "intention": plan.get("intention", ""),
                    "priority": plan.get("priority", "medium"),
                    "steps": plan.get("steps", []),
                    "abort_if": plan.get("abort_if", {}),
                    "think_aloud": plan.get("think_aloud", ""),
                    "say_to": plan.get("say_to", None),
                },
            }
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON from Ollama: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def poll_completed(self) -> list[tuple[str, dict]]:
        """Return all completed futures as (agent_id, response) tuples."""
        completed = []
        for agent_id, future in list(self._pending.items()):
            if future.done():
                try:
                    result = future.result()
                    completed.append((agent_id, result))
                except Exception as e:
                    completed.append((agent_id, {"success": False, "error": str(e)}))
                del self._pending[agent_id]
                self._pending_tasks.pop(agent_id, None)
        return completed
