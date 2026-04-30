"""Tests for the AI module: memory, prompts, and orchestrator."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.ai.memory import AgentMemory
from app.ai.prompts import build_agent_prompt, JSON_FORMAT_INSTRUCTION, SYSTEM_PROMPT_TEMPLATE
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

    def test_json_format_instruction_includes_all_actions(self):
        """JSON_FORMAT_INSTRUCTION contains all new actions."""
        actions = [
            "move", "chop", "drink", "eat", "gather", "rest",
            "mine", "explore", "craft", "hunt", "fish", "build",
            "farm", "attack", "guard", "heal", "trade", "socialize", "feed_child",
        ]
        for action in actions:
            assert f'"{action}"' in JSON_FORMAT_INSTRUCTION, f"missing action {action}"

    def test_system_prompt_mentions_structures_crafting_tools(self):
        """SYSTEM_PROMPT_TEMPLATE mentions structures, crafting, and tools."""
        prompt_lower = SYSTEM_PROMPT_TEMPLATE.lower()
        assert "structures" in prompt_lower
        assert "craft" in prompt_lower
        assert "tools" in prompt_lower

    def test_build_agent_prompt_includes_role_guidance_builder(self):
        """Prompt for builder includes construction guidance."""
        agent = Agent(id="test_001", name="Builder", position=(5.0, 5.0), role="builder")
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="",
            trigger="test",
        )
        assert "builder" in prompt.lower()
        assert "construction" in prompt.lower() or "build" in prompt.lower()

    def test_build_agent_prompt_includes_role_guidance_fighter(self):
        """Prompt for fighter includes combat guidance."""
        agent = Agent(id="test_001", name="Fighter", position=(5.0, 5.0), role="fighter")
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="",
            trigger="test",
        )
        assert "fighter" in prompt.lower()
        assert "defend" in prompt.lower() or "combat" in prompt.lower()

    def test_prompt_includes_nearby_structures(self):
        """Prompt includes NEARBY STRUCTURES section when structures are present."""
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="",
            trigger="test",
            nearby_structures="house at (3,3)",
        )
        assert "NEARBY STRUCTURES:" in prompt
        assert "house at (3,3)" in prompt

    def test_prompt_structures_empty_when_none(self):
        """Prompt shows (none) for nearby structures when empty."""
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="",
            trigger="test",
            nearby_structures="",
        )
        assert "NEARBY STRUCTURES:" in prompt
        assert "(none)" in prompt

    def test_prompt_includes_craftable_recipes(self):
        """Prompt includes CRAFTABLE RECIPES section when recipes provided."""
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0), role="crafter")
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="",
            trigger="test",
            craftable_recipes="stone_axe: wood:3, stone:2 -> stone_axe:1",
        )
        assert "CRAFTABLE RECIPES:" in prompt
        assert "stone_axe" in prompt

    def test_prompt_craftable_recipes_empty_when_none(self):
        """Prompt shows (none) for craftable recipes when empty."""
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="",
            trigger="test",
            craftable_recipes="",
        )
        assert "CRAFTABLE RECIPES:" in prompt
        assert "(none)" in prompt

    def test_prompt_includes_equipment(self):
        """Prompt includes EQUIPMENT section showing weapon, armor, tool."""
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.equipment = {"weapon": "spear", "armor": "hide_armor", "tool": "stone_axe"}
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="",
            trigger="test",
            equipment="weapon: spear, armor: hide_armor, tool: stone_axe",
        )
        assert "EQUIPMENT:" in prompt
        assert "spear" in prompt

    def test_prompt_includes_nearby_hostiles(self):
        """Prompt includes NEARBY HOSTILES section when hostiles provided."""
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="",
            trigger="test",
            nearby_hostiles="Enemy at (6,6)",
        )
        assert "NEARBY HOSTILES:" in prompt
        assert "Enemy" in prompt

    def test_prompt_hostiles_empty_when_none(self):
        """Prompt shows (none) for nearby hostiles when empty."""
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="",
            trigger="test",
            nearby_hostiles="",
        )
        assert "NEARBY HOSTILES:" in prompt
        assert "(none)" in prompt


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

    def test_orchestrator_includes_nearby_structures(self):
        """Orchestrator build_prompt includes nearby structures from the world."""
        from app.simulation.world import World
        from app.simulation.structures import Structure

        orchestrator = RealLLMOrchestrator()
        world = World(width=10, height=10)
        world.structures.add_structure(
            Structure(id="s1", structure_type="house", position=(3, 3))
        )
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        prompt = orchestrator.build_prompt(agent, world=world)
        assert "NEARBY STRUCTURES:" in prompt
        assert "house" in prompt.lower()

    def test_orchestrator_structures_empty_when_none(self):
        """Orchestrator build_prompt shows (none) when no structures nearby."""
        from app.simulation.world import World

        orchestrator = RealLLMOrchestrator()
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        prompt = orchestrator.build_prompt(agent, world=world)
        assert "NEARBY STRUCTURES:" in prompt
        assert "(none)" in prompt.lower()

    def test_orchestrator_includes_craftable_recipes(self):
        """Orchestrator build_prompt includes craftable recipes when agent has materials."""
        from app.simulation.world import World

        orchestrator = RealLLMOrchestrator()
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Crafter", position=(5.0, 5.0), role="crafter")
        agent.inventory = {"wood": 5, "stone": 5}
        prompt = orchestrator.build_prompt(agent, world=world)
        assert "CRAFTABLE RECIPES:" in prompt
        assert "stone_axe" in prompt

    def test_orchestrator_craftable_recipes_empty_for_non_crafter(self):
        """Orchestrator build_prompt shows no recipes for roles that cannot craft."""
        from app.simulation.world import World

        orchestrator = RealLLMOrchestrator()
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Gatherer", position=(5.0, 5.0), role="gatherer")
        agent.inventory = {"wood": 5, "stone": 5}
        prompt = orchestrator.build_prompt(agent, world=world)
        assert "CRAFTABLE RECIPES:" in prompt
        assert "(none)" in prompt.lower()

    def test_orchestrator_includes_equipment(self):
        """Orchestrator build_prompt includes equipment loadout."""
        from app.simulation.world import World

        orchestrator = RealLLMOrchestrator()
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.equipment = {"weapon": "spear", "armor": "hide_armor", "tool": "stone_axe"}
        prompt = orchestrator.build_prompt(agent, world=world)
        assert "EQUIPMENT:" in prompt
        assert "spear" in prompt.lower()

    def test_orchestrator_includes_nearby_hostiles(self):
        """Orchestrator build_prompt includes nearby hostile agents."""
        from app.simulation.world import World

        orchestrator = RealLLMOrchestrator()
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0), faction_id="faction_a")
        enemy = Agent(id="test_002", name="Enemy", position=(6.0, 6.0), faction_id="faction_b")
        agents = [agent, enemy]
        prompt = orchestrator.build_prompt(agent, world=world, agents=agents)
        assert "NEARBY HOSTILES:" in prompt
        assert "Enemy" in prompt

    def test_orchestrator_hostiles_empty_when_none(self):
        """Orchestrator build_prompt shows (none) when no hostiles nearby."""
        from app.simulation.world import World

        orchestrator = RealLLMOrchestrator()
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        prompt = orchestrator.build_prompt(agent, world=world)
        assert "NEARBY HOSTILES:" in prompt
        assert "(none)" in prompt.lower()
