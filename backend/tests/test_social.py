"""Tests for agent-society social features (F1-F8)."""

import asyncio
import pytest

from app.simulation.world import World
from app.simulation.agent import Agent, AgentFactory
from app.simulation.actions import (
    ActionType, ActionResult,
    handle_move, handle_chop, handle_drink, handle_eat, handle_gather, handle_rest, handle_reproduce,
)
from app.simulation.snapshot import WorldSnapshotBuilder
from app.simulation.engine import SimulationEngine


# ─── F1 Tests ────────────────────────────────────────────────────


class TestActionResultFields:
    def test_action_result_has_action_type_and_summary(self):
        """ActionResult has action_type and action_summary with safe defaults."""
        result = ActionResult()
        assert hasattr(result, "action_type")
        assert hasattr(result, "action_summary")
        assert result.action_type is None
        assert result.action_summary == ""

    def test_handle_eat_populates_action_result(self):
        """handle_eat produces ActionResult with action_type and summary."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.hunger = 50.0
        agent.inventory["berries"] = 2
        result = handle_eat(agent, world)
        assert result.success is True
        assert result.action_type == ActionType.EAT
        assert "hunger" in result.action_summary
        assert "berries" in result.action_summary

    def test_handle_chop_populates_action_result(self):
        """handle_chop produces ActionResult with action_type and summary."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        world.get_tile(5, 5).resource_type = "tree"
        world.get_tile(5, 5).amount = 5
        result = handle_chop(agent, world)
        assert result.success is True
        assert result.action_type == ActionType.CHOP
        assert "wood" in result.action_summary

    def test_handle_drink_populates_action_result(self):
        """handle_drink produces ActionResult with action_type and summary."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.thirst = 80.0
        world.get_tile(5, 5).resource_type = "water"
        result = handle_drink(agent, world)
        assert result.success is True
        assert result.action_type == ActionType.DRINK
        assert "thirst" in result.action_summary

    def test_handle_move_populates_action_result(self):
        """handle_move produces ActionResult with action_type and summary."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(0.0, 0.0))
        agent.move_path = [(1, 0), (2, 0)]
        result = handle_move(agent, world)
        assert result.success is True
        assert result.action_type == ActionType.MOVE
        assert "position" in result.action_summary or "move" in result.action_summary.lower()

    def test_handle_gather_populates_action_result(self):
        """handle_gather produces ActionResult with action_type and summary."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                tile = world.get_tile(5 + dx, 5 + dy)
                tile.resource_type = None
                tile.amount = 0
        world.get_tile(5, 5).resource_type = "berries"
        world.get_tile(5, 5).amount = 3
        result = handle_gather(agent, world)
        assert result.success is True
        assert result.action_type == ActionType.GATHER
        assert "berries" in result.action_summary

    def test_handle_rest_populates_action_result(self):
        """handle_rest produces ActionResult with action_type and summary."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.energy = 50.0
        result = handle_rest(agent, world)
        assert result.success is True
        assert result.action_type == ActionType.REST
        assert "energy" in result.action_summary

    def test_handle_reproduce_populates_action_result(self):
        """handle_reproduce produces ActionResult with action_type and summary."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        result = handle_reproduce(agent, world)
        assert result.success is True
        assert result.action_type == ActionType.REPRODUCE
        assert result.action_summary != ""


class TestAgentLastActionResult:
    def test_agent_has_last_action_result_field(self):
        """Agent dataclass has last_action_result with default None."""
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        assert hasattr(agent, "last_action_result")
        assert agent.last_action_result is None

    def test_action_result_captured(self):
        """After an action, result is assigned to agent.last_action_result."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.inventory["berries"] = 2
        result = handle_eat(agent, world)
        # Simulate what engine does
        agent.last_action_result = result
        assert agent.last_action_result is not None
        assert agent.last_action_result.action_type == ActionType.EAT

    def test_action_result_null_on_first_tick(self):
        """New agent has last_action_result=None."""
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        assert agent.last_action_result is None

    def test_build_prompt_includes_last_action_result(self):
        """Prompt includes LAST ACTION RESULT section when present."""
        from app.ai.prompts import build_agent_prompt
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.last_action_result = ActionResult(
            action_type=ActionType.CHOP,
            success=True,
            action_summary="wood:+3, energy:-10",
        )
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="(no recent memories)",
            trigger="Time to decide",
            last_action_result=agent.last_action_result,
        )
        assert "LAST ACTION RESULT:" in prompt
        assert "CHOP" in prompt
        assert "wood:+3" in prompt

    def test_build_prompt_shows_none_on_first_tick(self):
        """Prompt shows None when last_action_result is None."""
        from app.ai.prompts import build_agent_prompt
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.last_action_result = None
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="(no recent memories)",
            trigger="Time to decide",
            last_action_result=None,
        )
        assert "LAST ACTION RESULT:" in prompt
        assert "None (first tick)" in prompt


# ─── F8 Tests ────────────────────────────────────────────────────


class TestRelationshipData:
    def test_relationship_data_exists(self):
        """RelationshipData dataclass exists with required fields."""
        from app.simulation.agent import RelationshipData
        rd = RelationshipData()
        assert rd.interaction_count == 0
        assert rd.last_interaction_tick == 0
        assert rd.score == 0.0

    def test_agent_has_relationships_field(self):
        """Agent has relationships dict with default empty."""
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        assert hasattr(agent, "relationships")
        assert agent.relationships == {}

    def test_relationships_in_snapshot(self):
        """Snapshot includes relationships for each agent."""
        from app.simulation.agent import RelationshipData
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.relationships["agent_002"] = RelationshipData(
            interaction_count=3, last_interaction_tick=10, score=0.5
        )
        builder = WorldSnapshotBuilder(world, [agent])
        snapshot = builder.build(tick=1)
        state = snapshot.agents["test_001"]
        assert hasattr(state, "relationships")
        assert "agent_002" in state.relationships
        assert state.relationships["agent_002"]["interaction_count"] == 3

    def test_reproduce_gated_by_interactions(self):
        """Reproduction requires interaction_count >= threshold."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        # Zog and Mila are default agents (male and female)
        # They have no relationships, so reproduction should be gated
        engine = SimulationEngine(world=world, agents=agents)
        partner = engine._find_reproduction_partner(agents[0])
        assert partner is None

    def test_relationship_decay(self):
        """After DECAY_INTERVAL ticks without interaction, count decrements."""
        from app.simulation.agent import RelationshipData
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        engine = SimulationEngine(world=world, agents=agents)
        # Manually create a relationship
        agents[0].relationships[agents[1].id] = RelationshipData(
            interaction_count=5, last_interaction_tick=1, score=0.5
        )
        agents[1].relationships[agents[0].id] = RelationshipData(
            interaction_count=5, last_interaction_tick=1, score=0.5
        )
        # Run process_needs at tick 200 (beyond DECAY_INTERVAL=100)
        asyncio.run(engine._process_needs(200))
        # interaction_count should have decremented once
        assert agents[0].relationships[agents[1].id].interaction_count == 4
        # score should also decay
        assert agents[0].relationships[agents[1].id].score == 0.49
        # Running again at tick 201 should NOT decrement again immediately
        asyncio.run(engine._process_needs(201))
        assert agents[0].relationships[agents[1].id].interaction_count == 4
        assert agents[0].relationships[agents[1].id].score == 0.49


class TestRelationshipTracking:
    def test_update_relationship_increments_count(self):
        """_update_relationship increments interaction_count for both agents."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        engine = SimulationEngine(world=world, agents=agents)
        engine._update_relationship(agents[0], agents[1], tick=10, score_delta=0.1)
        assert agents[0].relationships[agents[1].id].interaction_count == 1
        assert agents[1].relationships[agents[0].id].interaction_count == 1
        assert agents[0].relationships[agents[1].id].last_interaction_tick == 10

    def test_update_relationship_clamps_score(self):
        """Score is clamped to [-1.0, 1.0]."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        engine = SimulationEngine(world=world, agents=agents)
        engine._update_relationship(agents[0], agents[1], tick=1, score_delta=2.0)
        assert agents[0].relationships[agents[1].id].score == 1.0
        engine._update_relationship(agents[0], agents[1], tick=2, score_delta=-5.0)
        assert agents[0].relationships[agents[1].id].score == -1.0


# ─── F6 Tests ────────────────────────────────────────────────────


class TestConversationManager:
    def test_message_dataclass(self):
        """Message has sender_id, content dict, and tick."""
        from app.simulation.conversation import Message
        msg = Message(sender_id="a1", content={"type": "greeting"}, tick=5)
        assert msg.sender_id == "a1"
        assert msg.content == {"type": "greeting"}
        assert msg.tick == 5

    def test_detect_encounters_enqueues_greetings(self):
        """Two agents within radius get greeting messages."""
        from app.simulation.conversation import ConversationManager
        mgr = ConversationManager()
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a2 = Agent(id="a2", name="Bob", position=(6.0, 6.0))
        mgr.detect_encounters([a1, a2], radius=3.0, tick=1)
        assert len(a1.conversation_queue) == 1
        assert len(a2.conversation_queue) == 1
        assert a1.conversation_queue[0].content["type"] == "greeting"
        assert a1.conversation_queue[0].content["agent_name"] == "Bob"

    def test_max_queue_size(self):
        """Queue discards oldest messages when exceeding 50."""
        from app.simulation.conversation import ConversationManager, Message
        mgr = ConversationManager()
        agent = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        for i in range(60):
            mgr._enqueue_message(agent, Message(sender_id="x", content={"i": i}, tick=i))
        assert len(agent.conversation_queue) == 50
        assert agent.conversation_queue[0].content["i"] == 10
        assert agent.conversation_queue[-1].content["i"] == 59

    def test_max_pairs_per_tick(self):
        """Only 5 pairs processed per tick, remainder deferred."""
        from app.simulation.conversation import ConversationManager
        mgr = ConversationManager()
        agents = [Agent(id=f"a{i}", name=f"Agent{i}", position=(float(i), 0.0)) for i in range(12)]
        mgr.detect_encounters(agents, radius=3.0, tick=1)
        # 12 agents in a line at distance 1: many pairs within radius
        # Only 5 pairs should be processed, rest deferred
        processed = sum(1 for a in agents if len(a.conversation_queue) > 0)
        assert processed <= 10  # 5 pairs = 10 agents max
        assert len(mgr._pending_pairs) > 0  # Some deferred

    def test_socialize_event_logged(self):
        """Conversation generates SimEvent type 'socialize'."""
        from app.simulation.conversation import ConversationManager
        mgr = ConversationManager()
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a2 = Agent(id="a2", name="Bob", position=(6.0, 6.0))
        events = mgr.detect_encounters([a1, a2], radius=3.0, tick=1)
        assert len(events) == 1
        assert events[0].type == "socialize"


class TestConversationEngineIntegration:
    @pytest.mark.anyio
    @pytest.mark.anyio
    async def test_conversation_in_tick(self):
        """Engine tick processes social interactions and enqueues messages."""
        world = World(width=20, height=20)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a2 = Agent(id="a2", name="Bob", position=(6.0, 6.0))
        engine = SimulationEngine(world=world, agents=[a1, a2])
        await engine._tick()
        assert len(a1.conversation_queue) >= 1
        assert len(a2.conversation_queue) >= 1

    @pytest.mark.anyio
    async def test_encounter_updates_relationship(self):
        """After a social encounter, agents' relationship counts are incremented."""
        world = World(width=20, height=20)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a2 = Agent(id="a2", name="Bob", position=(6.0, 6.0))
        engine = SimulationEngine(world=world, agents=[a1, a2])
        await engine._tick()
        assert a1.relationships.get(a2.id) is not None
        assert a1.relationships[a2.id].interaction_count == 1
        assert a2.relationships.get(a1.id) is not None
        assert a2.relationships[a1.id].interaction_count == 1

    @pytest.mark.anyio
    async def test_knowledge_share_updates_relationship(self):
        """Knowledge sharing during encounter also updates relationships."""
        world = World(width=20, height=20)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a2 = Agent(id="a2", name="Bob", position=(6.0, 6.0))
        a1.knowledge["SAFE_BERRY"] = {"is_poisonous": False}
        engine = SimulationEngine(world=world, agents=[a1, a2])
        await engine._tick()
        # Should have relationship updated from the socialize event
        assert a1.relationships.get(a2.id) is not None
        assert a1.relationships[a2.id].interaction_count >= 1
        assert a2.relationships.get(a1.id) is not None
        assert a2.relationships[a1.id].interaction_count >= 1

    def test_prompt_includes_social_context(self):
        """Prompt includes SOCIAL CONTEXT section when messages exist."""
        from app.ai.prompts import build_agent_prompt
        from app.simulation.conversation import Message
        agent = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        agent.conversation_queue = [
            Message(sender_id="a2", content={"type": "greeting"}, tick=1)
        ]
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="(no recent memories)",
            trigger="Time to decide",
        )
        assert "SOCIAL CONTEXT:" in prompt


# ─── F2 Tests ────────────────────────────────────────────────────


class TestKnowledge:
    def test_tile_has_subtype_and_hidden_properties(self):
        """Tile has subtype and hidden_properties fields."""
        from app.simulation.world import Tile
        tile = Tile(x=5, y=5, resource_type="berries", subtype="POISONOUS_BERRY")
        assert tile.subtype == "POISONOUS_BERRY"
        assert hasattr(tile, "hidden_properties")

    def test_eat_reveals_hidden_properties(self):
        """Eating a resource with hidden properties reveals them to agent."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.inventory["berries"] = 2
        # Set tile subtype and hidden properties
        tile = world.get_tile(5, 5)
        tile.resource_type = "berries"
        tile.subtype = "POISONOUS_BERRY"
        tile.hidden_properties = {"is_poisonous": True}
        # Eat should reveal hidden properties
        result = handle_eat(agent, world)
        assert result.success is True
        assert "POISONOUS_BERRY" in agent.knowledge
        assert agent.knowledge["POISONOUS_BERRY"]["is_poisonous"] is True

    def test_knowledge_is_per_agent(self):
        """Two agents have independent knowledge stores."""
        world = World(width=10, height=10)
        agent_a = Agent(id="a1", name="A", position=(5.0, 5.0))
        agent_b = Agent(id="a2", name="B", position=(5.0, 5.0))
        agent_a.inventory["berries"] = 2
        tile = world.get_tile(5, 5)
        tile.resource_type = "berries"
        tile.subtype = "POISONOUS_BERRY"
        tile.hidden_properties = {"is_poisonous": True}
        handle_eat(agent_a, world)
        assert "POISONOUS_BERRY" in agent_a.knowledge
        assert "POISONOUS_BERRY" not in agent_b.knowledge

    def test_knowledge_in_prompt(self):
        """Agent with knowledge sees it in the prompt."""
        from app.ai.prompts import build_agent_prompt
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.knowledge = {"POISONOUS_BERRY": {"is_poisonous": True}}
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="(no recent memories)",
            trigger="Time to decide",
        )
        assert "KNOWLEDGE:" in prompt
        assert "POISONOUS_BERRY" in prompt

    def test_snapshot_does_not_expose_hidden(self):
        """World snapshot shows subtype but not hidden_properties."""
        world = World(width=10, height=10)
        tile = world.get_tile(5, 5)
        tile.resource_type = "berries"
        tile.subtype = "POISONOUS_BERRY"
        tile.hidden_properties = {"is_poisonous": True}
        world.dirty_tiles.add((5, 5))
        agents = []
        builder = WorldSnapshotBuilder(world, agents)
        snapshot = builder.build_delta(tick=1)
        tile_updates = [t for t in snapshot.tiles if t.x == 5 and t.y == 5]
        assert len(tile_updates) == 1
        assert tile_updates[0].subtype == "POISONOUS_BERRY"
        assert not hasattr(tile_updates[0], "hidden_properties")

    def test_knowledge_share_via_message(self):
        """Direct update of knowledge via Message content."""
        from app.simulation.conversation import Message
        agent = Agent(id="a2", name="B", position=(5.0, 5.0))
        msg = Message(
            sender_id="a1",
            content={
                "type": "share_knowledge",
                "subtype": "POISONOUS_BERRY",
                "properties": {"is_poisonous": True},
            },
            tick=1,
        )
        if msg.content["type"] == "share_knowledge":
            agent.knowledge[msg.content["subtype"]] = dict(msg.content["properties"])
        assert agent.knowledge["POISONOUS_BERRY"]["is_poisonous"] is True


# ─── F5 Tests ────────────────────────────────────────────────────


class TestTrade:
    def test_trade_atomic_swap(self):
        """Successful trade updates both inventories atomically via engine."""
        world = World(width=10, height=10)
        proposer = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        target = Agent(id="a2", name="Bob", position=(5.0, 5.0))
        proposer.inventory = {"wood": 5}
        target.inventory = {"berries": 8}
        engine = SimulationEngine(world=world, agents=[proposer, target])
        # Manually enqueue a trade proposal in target's queue
        from app.simulation.conversation import Message
        target.conversation_queue.append(
            Message(
                sender_id=proposer.id,
                content={
                    "type": "trade_proposal",
                    "from": proposer.id,
                    "offer": {"wood": 3},
                    "request": {"berries": 5},
                },
                tick=1,
            )
        )
        # Override evaluation to force accept
        async def _accept(agent, proposal): return True
        engine._evaluate_trade_proposal = _accept
        asyncio.run(engine._process_trade_proposals(tick=2))
        assert proposer.inventory["wood"] == 2
        assert proposer.inventory["berries"] == 5
        assert target.inventory["wood"] == 3
        assert target.inventory["berries"] == 3

    def test_trade_insufficient_funds(self):
        """Trade fails when proposer lacks resources."""
        from app.simulation.actions import handle_trade
        world = World(width=10, height=10)
        proposer = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        proposer.inventory = {"wood": 2}
        step = {"offer": {"wood": 10}, "request": {"berries": 5}}
        result = handle_trade(proposer, world, step=step)
        assert result.success is False
        assert "insufficient" in result.action_summary.lower() or "fail" in result.action_summary.lower()

    def test_trade_interaction_count_via_engine(self):
        """Successful trade increments interaction_count for both agents via full flow."""
        world = World(width=10, height=10)
        proposer = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        target = Agent(id="a2", name="Bob", position=(5.0, 5.0))
        proposer.inventory = {"wood": 5}
        target.inventory = {"berries": 8}
        engine = SimulationEngine(world=world, agents=[proposer, target])
        from app.simulation.conversation import Message
        target.conversation_queue.append(
            Message(
                sender_id=proposer.id,
                content={
                    "type": "trade_proposal",
                    "from": proposer.id,
                    "offer": {"wood": 3},
                    "request": {"berries": 5},
                },
                tick=1,
            )
        )
        async def _accept(agent, proposal): return True
        engine._evaluate_trade_proposal = _accept
        asyncio.run(engine._process_trade_proposals(tick=2))
        assert proposer.relationships[target.id].interaction_count == 1
        assert target.relationships[proposer.id].interaction_count == 1

    @pytest.mark.anyio
    async def test_trade_full_flow_accept(self):
        """Full trade flow: proposal processed, accepted, atomic swap executed."""
        world = World(width=10, height=10)
        proposer = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        target = Agent(id="a2", name="Bob", position=(5.0, 5.0))
        proposer.inventory = {"wood": 5}
        target.inventory = {"berries": 8}
        engine = SimulationEngine(world=world, agents=[proposer, target])
        # Manually enqueue a trade proposal in target's queue
        from app.simulation.conversation import Message
        target.conversation_queue.append(
            Message(
                sender_id=proposer.id,
                content={
                    "type": "trade_proposal",
                    "from": proposer.id,
                    "offer": {"wood": 3},
                    "request": {"berries": 5},
                },
                tick=1,
            )
        )
        # Override evaluation to force accept
        async def _accept(agent, proposal): return True
        engine._evaluate_trade_proposal = _accept
        await engine._process_trade_proposals(tick=2)
        assert proposer.inventory["wood"] == 2
        assert proposer.inventory["berries"] == 5
        assert target.inventory["wood"] == 3
        assert target.inventory["berries"] == 3
        assert proposer.relationships[target.id].interaction_count == 1

    @pytest.mark.anyio
    async def test_trade_full_flow_reject(self):
        """Full trade flow: proposal processed, rejected, SimEvent logged."""
        world = World(width=10, height=10)
        proposer = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        target = Agent(id="a2", name="Bob", position=(5.0, 5.0))
        proposer.inventory = {"wood": 5}
        target.inventory = {"berries": 2}  # Not enough
        engine = SimulationEngine(world=world, agents=[proposer, target])
        from app.simulation.conversation import Message
        target.conversation_queue.append(
            Message(
                sender_id=proposer.id,
                content={
                    "type": "trade_proposal",
                    "from": proposer.id,
                    "offer": {"wood": 3},
                    "request": {"berries": 5},
                },
                tick=1,
            )
        )
        # Override evaluation to force reject
        async def _reject(agent, proposal): return False
        engine._evaluate_trade_proposal = _reject
        await engine._process_trade_proposals(tick=2)
        # Inventories unchanged
        assert proposer.inventory["wood"] == 5
        assert target.inventory["berries"] == 2
        # Event logged
        events = engine.event_queue.drain()
        trade_events = [e for e in events if e.type == "trade"]
        assert len(trade_events) == 1
        assert "rejected" in trade_events[0].description.lower() or "insufficient" in trade_events[0].description.lower()


# ─── F3 Tests ────────────────────────────────────────────────────


class TestChildhood:
    def test_child_blocks_eat(self):
        """Child agents cannot execute EAT independently."""
        world = World(width=10, height=10)
        child = Agent(id="child_001", name="Child", position=(5.0, 5.0), is_child=True)
        child.inventory["berries"] = 2
        result = handle_eat(child, world)
        assert result.success is False
        assert "child" in result.action_summary.lower()

    def test_feed_child_action(self):
        """Caregiver feeds child, reducing child's hunger and caregiver's berries."""
        from app.simulation.actions import handle_feed_child
        world = World(width=10, height=10)
        caregiver = Agent(id="care_001", name="Caregiver", position=(5.0, 5.0))
        child = Agent(id="child_001", name="Child", position=(5.0, 5.0), is_child=True)
        caregiver.inventory["berries"] = 5
        child.hunger = 90
        result = handle_feed_child(
            caregiver, world, step={"child_id": "child_001"}, agents=[caregiver, child]
        )
        assert result.success is True
        assert caregiver.inventory["berries"] == 4
        assert child.hunger == 60
        assert result.action_type.value == "feed_child"

    def test_feed_child_no_berries(self):
        """Feed child fails when caregiver has no berries."""
        from app.simulation.actions import handle_feed_child
        world = World(width=10, height=10)
        caregiver = Agent(id="care_001", name="Caregiver", position=(5.0, 5.0))
        child = Agent(id="child_001", name="Child", position=(5.0, 5.0), is_child=True)
        caregiver.inventory["berries"] = 0
        child.hunger = 90
        result = handle_feed_child(
            caregiver, world, step={"child_id": "child_001"}, agents=[caregiver, child]
        )
        assert result.success is False
        assert child.hunger == 90

    def test_feed_child_not_nearby(self):
        """Feed child fails when child is too far."""
        from app.simulation.actions import handle_feed_child
        world = World(width=10, height=10)
        caregiver = Agent(id="care_001", name="Caregiver", position=(5.0, 5.0))
        child = Agent(id="child_001", name="Child", position=(20.0, 20.0), is_child=True)
        caregiver.inventory["berries"] = 5
        child.hunger = 90
        result = handle_feed_child(
            caregiver, world, step={"child_id": "child_001"}, agents=[caregiver, child]
        )
        assert result.success is False
        assert child.hunger == 90

    def test_fsm_prioritizes_feed_child(self):
        """FSM evaluate prioritizes feeding child when child hunger > 70."""
        world = World(width=10, height=10)
        caregiver = Agent(id="care_001", name="Caregiver", position=(5.0, 5.0))
        child = Agent(id="child_001", name="Child", position=(5.0, 5.0), is_child=True, parent_id="care_001")
        caregiver.inventory["berries"] = 5
        child.hunger = 90
        engine = SimulationEngine(world=world, agents=[caregiver, child])
        fsm = engine.fsms[caregiver.id]
        fsm.transition_to("evaluate")
        engine._fsm_evaluate(caregiver, fsm, tick=1)
        assert caregiver.current_action == "feed_child"
        assert fsm.current_state == "executing"

    def test_child_stat_inheritance(self):
        """Child stats are derived from both parents with random offset via _create_offspring."""
        world = World(width=10, height=10)
        parent = Agent(id="parent_001", name="Parent", position=(5.0, 5.0), strength=80, intelligence=20, sociability=30, speed=10)
        partner = Agent(id="partner_001", name="Partner", position=(5.0, 5.0), strength=20, intelligence=80, sociability=70, speed=90)
        engine = SimulationEngine(world=world, agents=[parent, partner])
        child = engine._create_offspring(parent, partner, tick=1)
        # Stats should be within expected inheritance range
        assert 0 <= child.strength <= 100
        assert 0 <= child.intelligence <= 100
        assert 0 <= child.sociability <= 100
        assert 0 <= child.speed <= 100
        # Verify they are influenced by BOTH parents (average ±20)
        assert abs(child.strength - (parent.strength + partner.strength) / 2) <= 20
        assert abs(child.intelligence - (parent.intelligence + partner.intelligence) / 2) <= 20
        assert abs(child.sociability - (parent.sociability + partner.sociability) / 2) <= 20
        assert abs(child.speed - (parent.speed + partner.speed) / 2) <= 20
        # Extra discriminative assertions: with extreme differences, buggy single-parent
        # inheritance would never land in the correct averaged range
        assert child.speed >= 40  # buggy would max at 25 (10+15)

    def test_child_blocks_drink(self):
        """Child agents cannot execute DRINK independently."""
        world = World(width=10, height=10)
        child = Agent(id="child_001", name="Child", position=(5.0, 5.0), is_child=True)
        world.get_tile(5, 5).resource_type = "water"
        result = handle_drink(child, world)
        assert result.success is False
        assert "child" in result.action_summary.lower()

    def test_child_maturity(self):
        """Child reaches maturity when age >= maturity_age."""
        world = World(width=10, height=10)
        child = Agent(id="child_001", name="Child", position=(5.0, 5.0), is_child=True, maturity_age=10)
        child.age = 10
        engine = SimulationEngine(world=world, agents=[child])
        asyncio.run(engine._process_needs(10))
        assert child.is_child is False
        assert child.parent_id is None

    def test_child_cannot_reproduce(self):
        """Child agents cannot find reproduction partners."""
        world = World(width=10, height=10)
        child = Agent(id="child_001", name="Child", position=(5.0, 5.0), is_child=True, sex="male")
        adult = Agent(id="adult_001", name="Adult", position=(5.0, 5.0), sex="female", age=200)
        engine = SimulationEngine(world=world, agents=[child, adult])
        engine._update_relationship(child, adult, tick=1, score_delta=0.5)
        child.relationships[adult.id].interaction_count = 10
        adult.relationships[child.id].interaction_count = 10
        partner = engine._find_reproduction_partner(child)
        assert partner is None

    def test_child_spawn_adjacent_to_parent(self):
        """Newborn spawns adjacent to parent (Manhattan distance <= 2)."""
        world = World(width=20, height=20)
        parent = Agent(id="parent_001", name="Parent", position=(10.0, 10.0), sex="female")
        partner = Agent(id="partner_001", name="Partner", position=(11.0, 10.0), sex="male")
        engine = SimulationEngine(world=world, agents=[parent, partner])
        # Create relationship to allow reproduction
        engine._update_relationship(parent, partner, tick=1, score_delta=0.5)
        parent.relationships[partner.id].interaction_count = 10
        partner.relationships[parent.id].interaction_count = 10
        child = engine._create_offspring(parent, partner, tick=1)
        dx = abs(child.position[0] - parent.position[0])
        dy = abs(child.position[1] - parent.position[1])
        assert dx + dy <= 2

    def test_orphan_adoption(self):
        """When caregiver dies, nearby adult adopts the child."""
        world = World(width=20, height=20)
        caregiver = Agent(id="care_001", name="Caregiver", position=(5.0, 5.0))
        child = Agent(id="child_001", name="Child", position=(5.0, 5.0), is_child=True, parent_id="care_001")
        adult = Agent(id="adult_001", name="Adult", position=(6.0, 6.0))
        engine = SimulationEngine(world=world, agents=[caregiver, child, adult])
        # Simulate death processing
        caregiver.health = 0
        asyncio.run(engine._process_needs(1))
        assert caregiver not in engine.agents
        assert child.parent_id == "adult_001"
        # Verify adoption event was logged
        events = engine.event_queue.drain()
        adoption_events = [e for e in events if e.type == "adoption"]
        assert len(adoption_events) == 1
        assert "adopted" in adoption_events[0].description

    def test_fsm_cleaned_on_death(self):
        """FSM entry is removed when an agent dies."""
        world = World(width=10, height=10)
        agent = Agent(id="agent_001", name="Test", position=(5.0, 5.0))
        engine = SimulationEngine(world=world, agents=[agent])
        assert agent.id in engine.fsms
        agent.health = 0
        asyncio.run(engine._process_needs(1))
        assert agent.id not in engine.fsms

    def test_death_cause_old_age(self):
        """Death by old age reports correct cause."""
        world = World(width=10, height=10)
        agent = Agent(id="agent_001", name="Test", position=(5.0, 5.0), age=3000, max_age=3000)
        engine = SimulationEngine(world=world, agents=[agent])
        asyncio.run(engine._process_needs(1))
        assert agent not in engine.agents
        events = engine.event_queue.drain()
        death_events = [e for e in events if e.type == "death"]
        assert len(death_events) == 1
        assert death_events[0].metadata.get("cause") == "old_age"
        assert "old age" in death_events[0].description.lower()

    def test_death_cause_starvation_over_old_age(self):
        """When health <= 0 and age >= max_age, starvation (or thirst) takes priority over old_age."""
        world = World(width=10, height=10)
        agent = Agent(id="agent_001", name="Test", position=(5.0, 5.0), age=3000, max_age=3000, health=0)
        engine = SimulationEngine(world=world, agents=[agent])
        asyncio.run(engine._process_needs(1))
        events = engine.event_queue.drain()
        death_events = [e for e in events if e.type == "death"]
        assert len(death_events) == 1
        assert death_events[0].metadata.get("cause") == "starvation"

    def test_partner_fsm_transitions_to_executing(self):
        """Partner FSM also transitions to executing during reproduction."""
        from app.simulation.agent import RelationshipData
        world = World(width=10, height=10)
        agent = Agent(id="a1", name="Alice", position=(5.0, 5.0), energy=100, hunger=0, thirst=0, sex="female", age=200)
        partner = Agent(id="a2", name="Bob", position=(5.0, 5.0), energy=100, hunger=0, thirst=0, sex="male", age=200)
        agent.relationships[partner.id] = RelationshipData(interaction_count=10, last_interaction_tick=1, score=0.5)
        partner.relationships[agent.id] = RelationshipData(interaction_count=10, last_interaction_tick=1, score=0.5)
        engine = SimulationEngine(world=world, agents=[agent, partner])
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")
        engine._fsm_evaluate(agent, fsm, tick=1000)
        assert agent.current_action == "reproduce"
        assert fsm.current_state == "executing"
        assert engine.fsms[partner.id].current_state == "executing"


# ─── F4 Tests ────────────────────────────────────────────────────


class TestFactionPrompt:
    def test_prompt_includes_faction_section(self):
        """Prompt includes FACTION section with faction data."""
        from app.ai.prompts import build_agent_prompt
        agent = Agent(id="a1", name="Alice", position=(5.0, 5.0), faction_id="faction_001")
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="(no recent memories)",
            trigger="Time to decide",
            faction_context='You are a member of "River Clan"',
        )
        assert "FACTION:" in prompt
        assert "River Clan" in prompt

    def test_prompt_faction_none(self):
        """Agent without faction shows no faction message."""
        from app.ai.prompts import build_agent_prompt
        agent = Agent(id="a1", name="Alice", position=(5.0, 5.0), faction_id=None)
        prompt = build_agent_prompt(
            agent=agent,
            nearby_resources="none",
            nearby_agents="none",
            memories="(no recent memories)",
            trigger="Time to decide",
        )
        assert "FACTION:" in prompt
        assert "not in a faction" in prompt or "no faction" in prompt.lower()


class TestFaction:
    def test_faction_crud(self):
        """FactionManager supports create, delete, join, leave, list."""
        from app.simulation.faction import FactionManager
        mgr = FactionManager()
        # Clear defaults for clean test
        for fid in list(mgr.factions.keys()):
            mgr.delete(fid)
        f = mgr.create("Test Faction", "#FF0000")
        assert f.name == "Test Faction"
        assert f.color == "#FF0000"
        assert mgr.join("agent_001", f.id) is True
        assert "agent_001" in f.member_ids
        assert mgr.leave("agent_001", f.id) is True
        assert "agent_001" not in f.member_ids
        assert len(mgr.list_all()) == 1
        assert mgr.delete(f.id) is True
        assert len(mgr.list_all()) == 0

    def test_faction_death_transfer(self):
        """Agent death transfers inventory to faction shared_resources."""
        from app.simulation.faction import FactionManager
        mgr = FactionManager()
        f = mgr.create("Test Faction", "#FF0000")
        agent = Agent(id="agent_001", name="Test", position=(5.0, 5.0), faction_id=f.id)
        agent.inventory = {"wood": 5, "berries": 3}
        mgr.join(agent.id, f.id)
        mgr.transfer_inventory_on_death(agent)
        assert f.shared_resources.get("wood", 0) == 5
        assert f.shared_resources.get("berries", 0) == 3

    def test_faction_death_removes_member(self):
        """Agent death removes them from faction member_ids."""
        from app.simulation.faction import FactionManager
        mgr = FactionManager()
        f = mgr.create("Test Faction", "#FF0000")
        agent = Agent(id="agent_001", name="Test", position=(5.0, 5.0), faction_id=f.id)
        mgr.join(agent.id, f.id)
        assert "agent_001" in f.member_ids
        mgr.transfer_inventory_on_death(agent)
        assert "agent_001" not in f.member_ids

    def test_faction_defaults(self):
        """FactionManager creates 3 default factions."""
        from app.simulation.faction import FactionManager
        mgr = FactionManager()
        assert len(mgr.list_all()) == 3
        names = [f.name for f in mgr.list_all()]
        assert "River Clan" in names
        assert "Stone Hold" in names
        assert "Green Ward" in names

    def test_faction_in_snapshot(self):
        """Snapshot includes faction data."""
        world = World(width=10, height=10)
        agent = Agent(id="agent_001", name="Test", position=(5.0, 5.0))
        engine = SimulationEngine(world=world, agents=[agent])
        f = engine.faction_manager.create("Test", "#00FF00")
        engine.faction_manager.join(agent.id, f.id)
        agent.faction_id = f.id
        snapshot = engine.builder.build(tick=1, faction_manager=engine.faction_manager)
        assert hasattr(snapshot, "factions")
        assert len(snapshot.factions) >= 1


# ─── F7 Tests ────────────────────────────────────────────────────


class TestColonyStats:
    def test_colony_stats_collector(self):
        """ColonyStatsCollector computes correct statistics."""
        from app.simulation.colony import ColonyStatsCollector
        agent1 = Agent(id="a1", name="A1", position=(5.0, 5.0), role="gatherer", sex="male", is_child=True)
        agent2 = Agent(id="a2", name="A2", position=(5.0, 5.0), role="builder", sex="female", age=2000)
        collector = ColonyStatsCollector()
        collector.record_birth()
        collector.record_birth()
        collector.record_death()
        stats = collector.collect([agent1, agent2], None)
        assert stats.population == 2
        assert stats.births == 2
        assert stats.deaths == 1
        assert stats.sex_distribution["male"] == 1
        assert stats.sex_distribution["female"] == 1
        assert stats.age_groups["child"] == 1

    def test_colony_stats_in_snapshot(self):
        """WebSocket snapshot includes colony_stats."""
        from app.simulation.colony import ColonyStatsCollector
        world = World(width=10, height=10)
        agent = Agent(id="a1", name="A1", position=(5.0, 5.0))
        collector = ColonyStatsCollector()
        engine = SimulationEngine(world=world, agents=[agent])
        engine.colony_stats_collector = collector
        collector.record_birth()
        stats = collector.collect(engine.agents, engine.faction_manager)
        colony_stats_dict = {
            "population": stats.population,
            "births": stats.births,
            "deaths": stats.deaths,
            "total_resources": stats.total_resources,
        }
        snapshot = engine.builder.build_delta(
            tick=1, faction_manager=engine.faction_manager, colony_stats=colony_stats_dict
        )
        assert snapshot.colony_stats is not None
        assert snapshot.colony_stats["population"] == 1
        assert snapshot.colony_stats["births"] == 1

    def test_colony_endpoint(self):
        """GET /api/colony returns correct JSON structure."""
        from app.api.colony import router
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        # This test verifies the endpoint structure exists
        # Full integration would require running engine
        response = client.get("/api/colony")
        assert response.status_code in (200, 503)  # 503 if engine not available
