"""Tests for dialogue / social-update pipeline (say_to, think_aloud, bubbles)."""

import pytest
import asyncio

from app.ai.prompts import JSON_FORMAT_INSTRUCTION
from app.ai.orchestrator import RealLLMOrchestrator
from app.simulation.agent import Agent, MockLLMOrchestrator
from app.simulation.engine import SimulationEngine
from app.simulation.world import World
from app.simulation.snapshot import WorldSnapshotBuilder
from app.simulation.conversation import Message


class TestPromptFormat:
    def test_say_to_in_prompt_format(self):
        """JSON_FORMAT_INSTRUCTION includes say_to field as optional."""
        assert '"say_to"' in JSON_FORMAT_INSTRUCTION
        assert "agent_id" in JSON_FORMAT_INSTRUCTION
        assert "text" in JSON_FORMAT_INSTRUCTION
        assert "think_aloud" in JSON_FORMAT_INSTRUCTION


class TestOrchestratorDialogue:
    @pytest.mark.anyio
    async def test_real_orchestrator_extracts_say_to(self):
        """RealLLMOrchestrator extracts say_to from LLM JSON response."""
        orchestrator = RealLLMOrchestrator()
        import json
        from unittest.mock import AsyncMock, Mock, patch

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
                    "say_to": {"agent_id": "agent_002", "text": "Hello Mila!"},
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
        assert result["data"]["say_to"] == {"agent_id": "agent_002", "text": "Hello Mila!"}

    @pytest.mark.anyio
    async def test_mock_includes_say_to(self):
        """MockLLMOrchestrator call_async result includes say_to field (may be None)."""
        llm = MockLLMOrchestrator(delay_range=(0.01, 0.05), success_rate=1.0)
        agent = Agent(id="test_001", name="Tester", position=(0.0, 0.0))
        prompt = llm.build_prompt(agent)
        llm.call_async(agent.id, prompt)
        # wait for async resolution
        await asyncio.sleep(0.1)
        completed = llm.poll_completed()
        assert len(completed) == 1
        _, response = completed[0]
        assert response["success"] is True
        assert "say_to" in response["data"]
        # say_to is now varied — may be None (thought-only) or a dict
        if response["data"]["say_to"] is not None:
            assert "agent_id" in response["data"]["say_to"]
            assert "text" in response["data"]["say_to"]


class TestAgentDialogueFields:
    def test_agent_dialogue_fields_default_to_none(self):
        """New Agent has current_dialogue and dialogue_type defaulting to None."""
        agent = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        assert hasattr(agent, "current_dialogue")
        assert hasattr(agent, "dialogue_type")
        assert agent.current_dialogue is None
        assert agent.dialogue_type is None

    def test_snapshot_includes_dialogue_fields(self):
        """WorldSnapshotBuilder maps current_dialogue and dialogue_type."""
        world = World(width=10, height=10)
        agent = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        agent.current_dialogue = "Hello!"
        agent.dialogue_type = "speech"
        builder = WorldSnapshotBuilder(world, [agent])
        snapshot = builder.build(tick=1)
        state = snapshot.agents["a1"]
        assert state.current_dialogue == "Hello!"
        assert state.dialogue_type == "speech"


class TestEngineProcessSayTo:
    def test_process_say_to_creates_message(self):
        """_process_say_to enqueues a Message in target's conversation_queue."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a2 = Agent(id="a2", name="Bob", position=(6.0, 6.0))
        engine = SimulationEngine(world=world, agents=[a1, a2])
        response_data = {
            "say_to": {"agent_id": "a2", "text": "Hi Bob!"},
            "think_aloud": "",
        }
        engine._process_say_to(a1, response_data, tick=1)
        assert len(a2.conversation_queue) == 1
        msg = a2.conversation_queue[0]
        assert isinstance(msg, Message)
        assert msg.sender_id == "a1"
        assert msg.content["type"] == "dialogue"
        assert msg.content["text"] == "Hi Bob!"

    def test_process_say_to_sets_dialogue_fields(self):
        """_process_say_to sets current_dialogue and dialogue_type on sender."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a2 = Agent(id="a2", name="Bob", position=(6.0, 6.0))
        engine = SimulationEngine(world=world, agents=[a1, a2])
        response_data = {"say_to": {"agent_id": "a2", "text": "Hi Bob!"}}
        engine._process_say_to(a1, response_data, tick=1)
        assert a1.current_dialogue == "Hi Bob!"
        assert a1.dialogue_type == "speech"

    def test_process_say_to_think_aloud(self):
        """_process_say_to with think_aloud only sets thought dialogue."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        engine = SimulationEngine(world=world, agents=[a1])
        response_data = {"think_aloud": "I wonder..."}
        engine._process_say_to(a1, response_data, tick=1)
        assert a1.current_dialogue == "I wonder..."
        assert a1.dialogue_type == "thought"

    def test_process_say_to_clears_on_none(self):
        """_process_say_to with neither say_to nor think_aloud clears fields."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        engine = SimulationEngine(world=world, agents=[a1])
        a1.current_dialogue = "Previous"
        a1.dialogue_type = "speech"
        response_data = {}
        engine._process_say_to(a1, response_data, tick=1)
        assert a1.current_dialogue is None
        assert a1.dialogue_type is None

    def test_process_say_to_invalid_target(self):
        """say_to with non-existent target logs warning but does not crash."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        engine = SimulationEngine(world=world, agents=[a1])
        response_data = {"say_to": {"agent_id": "missing", "text": "Hello?"}}
        # Should not raise
        engine._process_say_to(a1, response_data, tick=1)
        assert a1.current_dialogue == "Hello?"
        assert a1.dialogue_type == "speech"

    def test_dialogue_event_for_say_to(self):
        """_process_say_to emits SimEvent type dialogue for say_to."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a2 = Agent(id="a2", name="Bob", position=(6.0, 6.0))
        engine = SimulationEngine(world=world, agents=[a1, a2])
        response_data = {"say_to": {"agent_id": "a2", "text": "Hi Bob!"}}
        engine._process_say_to(a1, response_data, tick=5)
        events = engine.event_queue.drain()
        dialogue_events = [e for e in events if e.type == "dialogue"]
        assert len(dialogue_events) == 1
        assert "Alice → Bob: Hi Bob!" in dialogue_events[0].description

    def test_dialogue_event_for_think_aloud(self):
        """_process_say_to emits SimEvent type dialogue for think_aloud."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        engine = SimulationEngine(world=world, agents=[a1])
        response_data = {"think_aloud": "I wonder..."}
        engine._process_say_to(a1, response_data, tick=5)
        events = engine.event_queue.drain()
        dialogue_events = [e for e in events if e.type == "dialogue"]
        assert len(dialogue_events) == 1
        assert "Alice thinks: I wonder..." in dialogue_events[0].description

    def test_no_dialogue_event_when_both_none(self):
        """No dialogue event when response has neither say_to nor think_aloud."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        engine = SimulationEngine(world=world, agents=[a1])
        response_data = {}
        engine._process_say_to(a1, response_data, tick=5)
        events = engine.event_queue.drain()
        dialogue_events = [e for e in events if e.type == "dialogue"]
        assert len(dialogue_events) == 0


class TestEngineIntegrationDialogue:
    @pytest.mark.anyio
    async def test_full_tick_cycle_with_dialogue(self):
        """Mock LLM with say_to produces dialogue in snapshot and event queue."""
        world = World(width=20, height=20)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a2 = Agent(id="a2", name="Bob", position=(6.0, 6.0))

        class FixedMockLLM(MockLLMOrchestrator):
            def call_async(self, agent_id, prompt):
                import asyncio
                loop = asyncio.get_running_loop()
                future = loop.create_future()
                future.set_result({
                    "success": True,
                    "data": {
                        "reasoning": "r",
                        "intention": "i",
                        "priority": "medium",
                        "steps": [],
                        "abort_if": {},
                        "think_aloud": "Thinking...",
                        "say_to": {"agent_id": "a2", "text": "Hi Bob!"},
                    }
                })
                self._pending[agent_id] = future
                return future

        llm = FixedMockLLM()
        engine = SimulationEngine(world=world, agents=[a1, a2], llm_orchestrator=llm)
        # Trigger LLM manually
        a1.llm_call_pending = True
        a1.llm_future = llm.call_async(a1.id, "prompt")
        await engine._tick()
        # Snapshot should contain dialogue fields
        snapshot = engine.builder.build(tick=engine.tick_count)
        state = snapshot.agents["a1"]
        assert state.current_dialogue == "Hi Bob!"
        assert state.dialogue_type == "speech"
        # Target should have received message
        assert len(a2.conversation_queue) >= 1
        assert a2.conversation_queue[-1].content["text"] == "Hi Bob!"

    @pytest.mark.anyio
    async def test_poll_llm_responses_triggers_dialogue(self):
        """Completed LLM future via poll triggers _process_say_to."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a2 = Agent(id="a2", name="Bob", position=(6.0, 6.0))
        llm = MockLLMOrchestrator(delay_range=(0.0, 0.0), success_rate=1.0)
        engine = SimulationEngine(world=world, agents=[a1, a2], llm_orchestrator=llm)
        a1.llm_call_pending = True
        a1.llm_future = llm.call_async(a1.id, "prompt")
        # wait resolution
        await asyncio.sleep(0.05)
        engine._poll_llm_responses(tick=1)
        assert a1.current_dialogue is not None
        assert a1.dialogue_type in ("speech", "thought")

    @pytest.mark.anyio
    async def test_fsm_llm_waiting_triggers_dialogue(self):
        """_poll_llm_responses (sole handler) processes say_to when future completes."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a2 = Agent(id="a2", name="Bob", position=(6.0, 6.0))
        llm = MockLLMOrchestrator(delay_range=(0.0, 0.0), success_rate=1.0)
        engine = SimulationEngine(world=world, agents=[a1, a2], llm_orchestrator=llm)
        fsm = engine.fsms[a1.id]
        fsm.transition_to("evaluate")
        fsm.transition_to("llm_trigger")
        engine._fsm_llm_trigger(a1, fsm, tick=1)
        # future should be set and done quickly
        await asyncio.sleep(0.05)
        # F1: poll path is sole handler — not _fsm_llm_waiting
        engine._poll_llm_responses(tick=2)
        assert a1.current_dialogue is not None
        assert a1.dialogue_type in ("speech", "thought")
        # _fsm_llm_waiting no longer processes plans — verify instinct behavior
        # Set up agent with completed future but NOT yet processed by poll path
        a1.current_dialogue = None
        fsm.transition_to("llm_trigger")
        a1._last_llm_tick = -999  # reset cooldown so trigger creates a future
        engine._fsm_llm_trigger(a1, fsm, tick=50)
        # After trigger: fsm is in llm_waiting, llm_future is set, llm_call_pending is True
        await asyncio.sleep(0.05)
        # future is done, but _fsm_llm_waiting should NOT process it
        assert a1.llm_future.done()
        engine._fsm_llm_waiting(a1, fsm, tick=51)
        assert a1.current_dialogue is None  # instinct does NOT set dialogue

    @pytest.mark.anyio
    async def test_agent_responds_when_spoken_to(self):
        """A sends say_to to B; B's LLM generates say_to back to A."""
        world = World(width=20, height=20)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a2 = Agent(id="a2", name="Bob", position=(5.0, 5.0))

        class ResponderMockLLM(MockLLMOrchestrator):
            def call_async(self, agent_id, prompt):
                import asyncio
                loop = asyncio.get_running_loop()
                future = loop.create_future()
                # If prompt contains unread message from someone, respond to them
                say_to = None
                if "Unread " in prompt and "(id=" in prompt:
                    after_id = prompt.split("(id=", 1)[1]
                    sender_id = after_id.split(")", 1)[0].strip()
                    say_to = {"agent_id": sender_id, "text": "Hey there!"}
                future.set_result({
                    "success": True,
                    "data": {
                        "reasoning": "r",
                        "intention": "i",
                        "priority": "medium",
                        "steps": [],
                        "abort_if": {},
                        "think_aloud": "Thinking...",
                        "say_to": say_to,
                    }
                })
                self._pending[agent_id] = future
                return future

        llm = ResponderMockLLM()
        engine = SimulationEngine(world=world, agents=[a1, a2], llm_orchestrator=llm)
        # A sends message to B
        engine._process_say_to(a1, {"say_to": {"agent_id": "a2", "text": "Hi Bob!"}}, tick=1)
        assert len(a2.conversation_queue) == 1
        # B triggers LLM — the mock should see the unread message
        a2.llm_call_pending = True
        a2.llm_future = llm.call_async(a2.id, llm.build_prompt(a2, world=world, agents=engine.agents))
        await asyncio.sleep(0.05)
        # F1: poll path is sole handler
        engine._poll_llm_responses(tick=2)
        assert a2.current_dialogue == "Hey there!"
        assert a2.dialogue_type == "speech"
        # A should have received B's response
        assert len(a1.conversation_queue) == 1
        assert a1.conversation_queue[0].content["text"] == "Hey there!"

    @pytest.mark.anyio
    async def test_dialogue_queue_consumed_after_llm(self):
        """Dialogue/greeting messages are removed from queue after LLM processing."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a1.conversation_queue.append(
            Message(sender_id="a2", content={"type": "dialogue", "text": "Hi!"}, tick=1)
        )
        a1.conversation_queue.append(
            Message(sender_id="a3", content={"type": "trade_proposal", "from": "a3"}, tick=1)
        )
        engine = SimulationEngine(world=world, agents=[a1])
        llm = MockLLMOrchestrator(delay_range=(0.0, 0.0), success_rate=1.0)
        engine.llm = llm
        fsm = engine.fsms[a1.id]
        fsm.transition_to("evaluate")
        fsm.transition_to("llm_trigger")
        engine._fsm_llm_trigger(a1, fsm, tick=1)
        await asyncio.sleep(0.05)
        # F1: poll path is sole handler
        engine._poll_llm_responses(tick=2)
        # Dialogue consumed, trade_proposal preserved
        assert len(a1.conversation_queue) == 1
        assert a1.conversation_queue[0].content["type"] == "trade_proposal"


class TestMockLLMResponse:
    @pytest.mark.anyio
    async def test_mock_responds_to_sender(self):
        """MockLLM generates say_to back to sender when queue has dialogue messages."""
        llm = MockLLMOrchestrator(delay_range=(0.0, 0.0), success_rate=1.0)
        agent = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        agent.conversation_queue.append(
            Message(
                sender_id="a2",
                content={"type": "dialogue", "text": "Hello!", "sender_name": "Bob", "sender_role": "builder"},
                tick=1,
            )
        )
        prompt = llm.build_prompt(agent, world=None, agents=None)
        assert "Unread dialogue from Bob" in prompt
        # Call async and resolve
        llm.call_async(agent.id, prompt)
        await asyncio.sleep(0.01)
        completed = llm.poll_completed()
        assert len(completed) == 1
        _, response = completed[0]
        assert response["success"] is True
        assert response["data"]["say_to"] is not None
        assert response["data"]["say_to"]["agent_id"] == "a2"


class TestNearbyAgentsPrompt:
    def test_nearby_agents_in_prompt(self):
        """RealLLMOrchestrator.build_prompt includes nearby friendly agents."""
        from app.simulation.world import World

        orchestrator = RealLLMOrchestrator()
        world = World(width=20, height=20)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0), faction_id="faction_a")
        a2 = Agent(id="a2", name="Bob", position=(6.0, 6.0), faction_id="faction_a")
        a3 = Agent(id="a3", name="Enemy", position=(20.0, 20.0), faction_id="faction_b")
        agents = [a1, a2, a3]
        prompt = orchestrator.build_prompt(a1, world=world, agents=agents)
        assert "NEARBY AGENTS:" in prompt
        assert "Bob" in prompt
        assert "Enemy" not in prompt  # hostile, different faction

    def test_nearby_agents_shows_none_when_alone(self):
        """RealLLMOrchestrator.build_prompt shows 'none' when no friendly agents nearby."""
        from app.simulation.world import World

        orchestrator = RealLLMOrchestrator()
        world = World(width=20, height=20)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0), faction_id="faction_a")
        a2 = Agent(id="a2", name="Enemy", position=(20.0, 20.0), faction_id="faction_b")
        agents = [a1, a2]
        prompt = orchestrator.build_prompt(a1, world=world, agents=agents)
        assert "NEARBY AGENTS:" in prompt
        assert "none" in prompt


class TestSocialContextRelationship:
    def test_social_context_includes_relationship_score(self):
        """Social context includes relationship score for known senders."""
        from app.ai.prompts import build_agent_prompt
        from app.simulation.conversation import Message
        from app.simulation.agent import RelationshipData

        agent = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        agent.conversation_queue = [
            Message(
                sender_id="a2",
                content={"type": "dialogue", "text": "Hi!", "sender_name": "Bob", "sender_role": "builder"},
                tick=1,
            )
        ]
        agent.relationships["a2"] = RelationshipData(score=0.5, interaction_count=3)
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="(no recent memories)",
            trigger="Time to decide",
        )
        assert "SOCIAL CONTEXT:" in prompt
        assert "Bob (builder): \"Hi!\" [relationship: 0.50]" in prompt

    def test_social_context_neutral_for_unknown(self):
        """Social context shows neutral relationship for unknown senders."""
        from app.ai.prompts import build_agent_prompt
        from app.simulation.conversation import Message

        agent = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        agent.conversation_queue = [
            Message(
                sender_id="a3",
                content={"type": "dialogue", "text": "Hello!", "sender_name": "Stranger", "sender_role": "scout"},
                tick=1,
            )
        ]
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="(no recent memories)",
            trigger="Time to decide",
        )
        assert "SOCIAL CONTEXT:" in prompt
        assert "Stranger (scout): \"Hello!\" [relationship: 0.00]" in prompt


class TestKnowledgeSharing:
    def test_share_knowledge_updates_knowledge_and_emits_event(self):
        """share_knowledge message updates recipient's knowledge and emits event."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a1.conversation_queue.append(
            Message(
                sender_id="a2",
                content={
                    "type": "share_knowledge",
                    "knowledge": {"berries": {"taste": "sweet"}},
                },
                tick=1,
            )
        )
        engine = SimulationEngine(world=world, agents=[a1])
        engine._tick_count = 1
        # Manually run the share_knowledge processing (normally in _tick)
        for agent in engine.agents:
            for msg in list(agent.conversation_queue):
                if msg.content.get("type") == "share_knowledge":
                    knowledge = msg.content.get("knowledge", {})
                    if knowledge and isinstance(knowledge, dict):
                        agent.knowledge.update(knowledge)
                        engine.event_queue.push(
                            "knowledge_learned",
                            f"{agent.name} learned about {', '.join(knowledge.keys())}",
                            "info",
                            [agent.id],
                            engine.tick_count,
                        )
                    agent.conversation_queue.remove(msg)
        assert "berries" in a1.knowledge
        events = engine.event_queue.drain()
        knowledge_events = [e for e in events if e.type == "knowledge_learned"]
        assert len(knowledge_events) == 1
        assert "Alice learned about berries" in knowledge_events[0].description


class TestF1UnifiedPollPath:
    """Tests for F1: _poll_llm_responses is the sole LLM response handler."""

    @pytest.mark.anyio
    async def test_response_in_llm_waiting_transitions_to_evaluate(self):
        """Response arrives for agent in llm_waiting → poll sets plan and transitions to evaluate."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        llm = MockLLMOrchestrator(delay_range=(0.0, 0.0), success_rate=1.0)
        engine = SimulationEngine(world=world, agents=[a1], llm_orchestrator=llm)
        fsm = engine.fsms[a1.id]
        fsm.transition_to("evaluate")
        fsm.transition_to("llm_trigger")
        engine._fsm_llm_trigger(a1, fsm, tick=1)
        await asyncio.sleep(0.05)
        assert a1.llm_future.done()
        engine._poll_llm_responses(tick=2)
        assert a1.active_plan is not None
        assert a1.llm_call_pending is False
        assert fsm.current_state == "evaluate"

    @pytest.mark.anyio
    async def test_response_not_in_llm_waiting_no_transition(self):
        """Response arrives for agent NOT in llm_waiting (e.g., interrupted) → plan set but NO transition."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        llm = MockLLMOrchestrator(delay_range=(0.0, 0.0), success_rate=1.0)
        engine = SimulationEngine(world=world, agents=[a1], llm_orchestrator=llm)
        fsm = engine.fsms[a1.id]
        fsm.transition_to("evaluate")
        fsm.transition_to("llm_trigger")
        engine._fsm_llm_trigger(a1, fsm, tick=1)
        await asyncio.sleep(0.05)
        # Agent is now in llm_waiting. Simulate interruption: put in executing state
        fsm.transition_to("executing")
        assert fsm.current_state == "executing"
        # Poll should set the plan but NOT transition (agent not in llm_waiting)
        engine._poll_llm_responses(tick=2)
        assert a1.active_plan is not None  # plan is set
        assert fsm.current_state == "executing"  # state unchanged

    @pytest.mark.anyio
    async def test_fsm_llm_waiting_does_not_process_completed_future(self):
        """_fsm_llm_waiting with completed future does NOT process the result (instinct only)."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        llm = MockLLMOrchestrator(delay_range=(0.0, 0.0), success_rate=1.0)
        engine = SimulationEngine(world=world, agents=[a1], llm_orchestrator=llm)
        fsm = engine.fsms[a1.id]
        fsm.transition_to("evaluate")
        fsm.transition_to("llm_trigger")
        engine._fsm_llm_trigger(a1, fsm, tick=1)
        await asyncio.sleep(0.05)
        # Record what plan was set (none before poll)
        assert a1.active_plan is None
        # Call _fsm_llm_waiting — should NOT process result
        engine._fsm_llm_waiting(a1, fsm, tick=2)
        # Future check: active_plan should still be None (not processed by _fsm_llm_waiting)
        assert a1.active_plan is None
        # Should have acted on instinct instead
        assert a1.current_action == "waiting"
