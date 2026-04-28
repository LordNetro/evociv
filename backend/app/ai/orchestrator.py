"""Real LLM orchestrator using LiteLLM with mock fallback."""

import asyncio
import json
import logging
import time
from typing import Optional

from app.core.config import settings
from app.simulation.agent import Agent, MockLLMOrchestrator
from app.ai.prompts import build_agent_prompt
from app.ai.memory import AgentMemory

logger = logging.getLogger("evociv.llm")
logger.setLevel(logging.WARNING)

try:
    import litellm
    litellm.set_verbose = False
    HAS_LITELLM = True
except ImportError:
    HAS_LITELLM = False
    logger.warning("LiteLLM not installed. Real LLM calls will fail.")


class RealLLMOrchestrator:
    """Orchestrates LLM calls via LiteLLM with the same interface as MockLLMOrchestrator.

    Falls back to MockLLMOrchestrator if the real LLM is unavailable and
    settings.llm_fallback_to_mock is True.
    """

    def __init__(
        self,
        model: str = "ollama/llama3.2",
        base_url: str = "http://localhost:11434",
        timeout: int = 30,
        memory: Optional[AgentMemory] = None,
    ):
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.memory = memory or AgentMemory()
        self._pending: dict[str, asyncio.Future] = {}
        self._mock = MockLLMOrchestrator()

        # Track whether the real LLM connection works
        self._real_available = None  # None = untested, True/False = tested
        self._last_test_time = 0
        self._test_interval = 60  # retest every 60s after failure

    def build_prompt(self, agent: Agent, world=None) -> str:
        """Build prompt with agent state, memories, and nearby info."""
        nearby_resources = "none"
        nearby_agents_str = "none"
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
            nearby_agents=nearby_agents_str,
            memories=memories,
            trigger=trigger,
        )

    async def check_availability(self) -> bool:
        """Test if the LLM backend is reachable."""
        now = time.monotonic()
        if self._real_available is not None and now - self._last_test_time < self._test_interval:
            return self._real_available

        self._last_test_time = now
        try:
            # LiteLLM doesn't have a health check, so we try a minimal completion
            await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": "Respond with OK"}],
                max_tokens=5,
                timeout=5,
            )
            self._real_available = True
            logger.info(f"LLM backend available: {self.model}")
            return True
        except Exception as e:
            self._real_available = False
            logger.warning(f"LLM backend unavailable ({e}). Will use mock.")
            return False

    def call_async(self, agent_id: str, prompt: str) -> asyncio.Future:
        """Call LLM asynchronously. Returns a Future that resolves with the response.
        
        NOTE: This is NOT an async function. It creates a Future, launches a background
        task, and returns the Future immediately (matching MockLLMOrchestrator's interface).
        """
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[agent_id] = future

        async def _resolve() -> None:
            try:
                # Try real LLM
                if settings.llm_enabled and await self.check_availability():
                    result = await self._call_real_llm(prompt)
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
                if settings.llm_fallback_to_mock:
                    logger.debug(f"LLM call failed ({e}), using mock fallback for {agent_id}")
                    mock_future = self._mock.call_async(agent_id, prompt)
                    mock_result = await mock_future
                    future.set_result(mock_result)
                else:
                    future.set_result({"success": False, "error": str(e)})

        asyncio.create_task(_resolve())
        return future

    async def _call_real_llm(self, prompt: str) -> dict:
        """Make the actual LiteLLM call."""
        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=512,
                temperature=0.7,
                timeout=self.timeout,
                api_base=self.base_url,
            )

            content = response.choices[0].message.content
            # Parse JSON from response
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
        except json.JSONDecodeError:
            return {"success": False, "error": "LLM returned invalid JSON"}
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
