"""Tests for the AI module: memory, prompts, and orchestrator."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.ai.memory import AgentMemory
from app.ai.prompts import build_agent_prompt
from app.ai.orchestrator import RealLLMOrchestrator
from app.simulation.agent import Agent


# ─── Memory Tests ─────────────────────────────────────────────────


class TestAgentMemory:
    def test_memory_add_and_retrieve(self):
        """Memories can be added and retrieved."""
        memory = AgentMemory(max_per_agent=5)
        memory.add("agent_001", tick=1, summary="Chopped a tree", type="action")
        memory.add("agent_001", tick=2, summary="Drank water", type="action")
        entries = memory.get_recent("agent_001", n=5)
        assert len(entries) == 2
        assert entries[0].summary == "Chopped a tree"
        assert entries[1].summary == "Drank water"

    def test_memory_fifo_eviction(self):
        """Oldest memory is evicted when max size is exceeded."""
        memory = AgentMemory(max_per_agent=3)
        memory.add("agent_001", tick=1, summary="First")
        memory.add("agent_001", tick=2, summary="Second")
        memory.add("agent_001", tick=3, summary="Third")
        memory.add("agent_001", tick=4, summary="Fourth")
        entries = memory.get_recent("agent_001", n=5)
        assert len(entries) == 3
        assert entries[0].summary == "Second"
        assert entries[-1].summary == "Fourth"

    def test_memory_format_recent(self):
        """Recent memories are formatted correctly."""
        memory = AgentMemory()
        memory.add("agent_001", tick=5, summary="Met Alice", type="encounter")
        formatted = memory.format_recent("agent_001", n=5)
        assert "[encounter] tick 5: Met Alice" in formatted

    def test_memory_clear(self):
        """Clearing memory removes all entries for an agent."""
        memory = AgentMemory()
        memory.add("agent_001", tick=1, summary="Test")
        memory.clear("agent_001")
        assert memory.get_recent("agent_001") == []

    def test_memory_empty_format(self):
        """Formatting empty memory returns the placeholder string."""
        memory = AgentMemory()
        assert memory.format_recent("agent_001") == "(no recent memories)"


# ─── Prompts Tests ────────────────────────────────────────────────


class TestBuildAgentPrompt:
    def test_build_agent_prompt_structure(self):
        """Prompt contains system prompt, state, and JSON instruction."""
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="(no recent memories)",
            trigger="Time to decide",
        )
        assert "You are Tester" in prompt
        assert "CURRENT STATE:" in prompt
        assert "Respond with ONLY this JSON format:" in prompt

    def test_build_agent_prompt_with_memories(self):
        """Prompt includes recent memories."""
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="- [action] tick 1: Chopped a tree",
            trigger="Time to decide",
        )
        assert "RECENT MEMORIES:" in prompt
        assert "Chopped a tree" in prompt


# ─── Orchestrator Tests ───────────────────────────────────────────


class TestRealLLMOrchestrator:
    @pytest.mark.anyio
    async def test_ollama_success(self):
        """Mock a successful Ollama response and verify plan returned."""
        orchestrator = RealLLMOrchestrator()

        mock_response = Mock()
        mock_response.json.return_value = {
            "message": {
                "content": json.dumps({
                    "reasoning": "I need wood",
                    "intention": "Chop trees",
                    "priority": "high",
                    "steps": [],
                    "abort_if": {},
                    "think_aloud": "Let's chop",
                })
            }
        }
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.ai.orchestrator.httpx.AsyncClient", return_value=mock_client):
            result = await orchestrator._call_ollama("test prompt")

        assert result["success"] is True
        assert result["data"]["intention"] == "Chop trees"

    @pytest.mark.anyio
    async def test_ollama_timeout(self):
        """Mock a timeout and verify error response."""
        orchestrator = RealLLMOrchestrator()

        mock_client = AsyncMock()
        mock_client.post.side_effect = asyncio.TimeoutError("Connection timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.ai.orchestrator.httpx.AsyncClient", return_value=mock_client):
            result = await orchestrator._call_ollama("test prompt")

        assert result["success"] is False
        assert "timed out" in result["error"].lower() or "timeout" in result["error"].lower()

    @pytest.mark.anyio
    async def test_ollama_invalid_json(self):
        """Mock invalid JSON response and verify error response."""
        orchestrator = RealLLMOrchestrator()

        mock_response = Mock()
        mock_response.json.return_value = {
            "message": {
                "content": "not valid json {"
            }
        }
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.ai.orchestrator.httpx.AsyncClient", return_value=mock_client):
            result = await orchestrator._call_ollama("test prompt")

        assert result["success"] is False
        assert "Invalid JSON" in result["error"]
