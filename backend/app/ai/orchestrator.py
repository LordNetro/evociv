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
logger.setLevel(logging.WARNING)


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
    ):
        self.model = model
        self.api_url = f"{base_url.rstrip('/')}/api/chat"
        self.timeout = timeout
        self.memory = memory or AgentMemory()
        self._pending: dict[str, asyncio.Future] = {}
        self._mock = MockLLMOrchestrator()

        # Track whether the real LLM connection works
        self._real_available: Optional[bool] = None
        self._last_test_time = 0
        self._test_interval = 60

    @property
    def is_available(self) -> Optional[bool]:
        """Public read-only: None=untested, True=up, False=down."""
        return self._real_available

    def build_prompt(self, agent: Agent, world=None) -> str:
        """Build prompt with agent state, memories, and nearby info."""
        nearby_resources = "none"
        if world:
            resources = world.get_nearby_resources(agent.position, radius=5)
            if resources:
                nearby_resources = "; ".join(
                    f"{r[2]} at ({r[0]},{r[1]}) amount={r[3]}" for r in resources[:5]
                )
        memories = self.memory.format_recent(agent.id, n=5)
        trigger = agent.last_thought or "Time to decide what to do"
        return build_agent_prompt(
            agent=agent,
            nearby_resources=nearby_resources,
            nearby_agents="none",
            memories=memories,
            trigger=trigger,
        )

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
                if settings.llm_enabled and await self.check_availability():
                    result = await self._call_ollama(prompt)
                else:
                    raise RuntimeError("LLM disabled or unavailable")

                if result.get("success"):
                    plan = result.get("data", {})
                    intention = plan.get("intention", "")
                    reasoning = plan.get("reasoning", "")
                    if intention:
                        self.memory.add_thought(agent_id, 0, f"Planned: {intention}. {reasoning}")
                future.set_result(result)

            except Exception as e:
                logger.warning(f"Ollama _resolve exception for {agent_id}: {type(e).__name__}: {e}")
                if settings.llm_fallback_to_mock:
                    logger.debug(f"Mock fallback for {agent_id}")
                    mock_future = self._mock.call_async(agent_id, prompt)
                    mock_result = await mock_future
                    future.set_result(mock_result)
                else:
                    future.set_result({"success": False, "error": str(e)})

        asyncio.create_task(_resolve())
        return future

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
        return completed
