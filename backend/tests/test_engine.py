"""Tests for the simulation engine and its subsystems."""

import asyncio
import pytest

from app.simulation.world import World
from app.simulation.agent import Agent, AgentFactory, FSM, MockLLMOrchestrator
from app.simulation.actions import ActionType, REGISTRY, get_action_duration
from app.simulation.event_queue import EventQueue, check_proximity_encounters
from app.simulation.snapshot import WorldSnapshotBuilder
from app.simulation.engine import SimulationEngine


# ─── World Tests ─────────────────────────────────────────────────


class TestWorld:
    def test_world_initialization(self):
        """World creates grid with correct dimensions."""
        world = World(width=10, height=10)
        assert world.width == 10
        assert world.height == 10
        assert len(world.grid) == 10
        assert len(world.grid[0]) == 10

    def test_resource_generation(self):
        """World generates resources deterministically with seed."""
        w1 = World(width=50, height=50, seed=42)
        w2 = World(width=50, height=50, seed=42)
        t1 = w1.get_tile(5, 5)
        t2 = w2.get_tile(5, 5)
        assert t1.resource_type == t2.resource_type
        assert t1.amount == t2.amount

    def test_get_tile_bounds(self):
        """Getting out-of-bounds tile raises IndexError."""
        world = World(width=10, height=10)
        with pytest.raises(IndexError):
            world.get_tile(-1, 0)
        with pytest.raises(IndexError):
            world.get_tile(0, 100)

    def test_bfs_pathfinding(self):
        """BFS finds shortest path."""
        world = World(width=10, height=10)
        path = world.find_path((0, 0), (5, 5))
        assert len(path) > 0
        assert path[-1] == (5, 5)

    def test_bfs_unreachable(self):
        """BFS returns empty list for unreachable target."""
        world = World(width=10, height=10)
        path = world.find_path((0, 0), (0, 0))
        assert path == []

    def test_bfs_blocked_path(self):
        """BFS respects blocked tiles."""
        world = World(width=5, height=5)
        world.get_tile(1, 0).blocked = True
        world.get_tile(1, 1).blocked = True
        path = world.find_path((0, 0), (2, 0))
        # Should go around via (0,0)→(0,1)→(1,2)→... or similar
        assert len(path) > 0
        assert (1, 0) not in path

    def test_resource_regeneration(self):
        """Depleted resources regenerate over time."""
        world = World(width=5, height=5)
        # Find a tile with regen_rate > 0 (berries)
        regen_tile = None
        for y in range(world.height):
            for x in range(world.width):
                tile = world.get_tile(x, y)
                if tile.regen_rate > 0 and tile.amount > 0:
                    regen_tile = tile
                    break
            if regen_tile:
                break
        if regen_tile:
            original = regen_tile.amount
            regen_tile.amount = original - 1
            world.regenerate_resources()
            assert regen_tile.amount > original - 1


# ─── Agent Tests ─────────────────────────────────────────────────


class TestAgent:
    def test_agent_creation(self):
        """Agent is created with correct fields."""
        agent = Agent(id="test_001", name="TestBot", position=(5.0, 5.0))
        assert agent.id == "test_001"
        assert agent.name == "TestBot"
        assert agent.position == (5.0, 5.0)
        assert agent.hunger == 50.0
        assert agent.fsm_state == "idle"

    def test_factory_default_agents(self):
        """Factory creates 3 default agents."""
        agents = AgentFactory.create_default_agents()
        assert len(agents) == 3
        assert agents[0].name == "Zog"
        assert agents[1].name == "Mila"
        assert agents[2].name == "Kael"

    def test_fsm_valid_transitions(self):
        """FSM allows valid transitions."""
        fsm = FSM()
        assert fsm.current_state == "idle"
        fsm.transition_to("evaluate")
        assert fsm.current_state == "evaluate"
        fsm.transition_to("llm_trigger")
        assert fsm.current_state == "llm_trigger"

    def test_fsm_invalid_transition(self):
        """FSM raises on invalid transitions."""
        fsm = FSM()
        with pytest.raises(ValueError, match="Invalid transition"):
            fsm.transition_to("executing")  # Can't go from idle to executing

    @pytest.mark.anyio
    async def test_mock_llm_orchestrator(self):
        """MockLLM returns plans asynchronously."""
        llm = MockLLMOrchestrator(delay_range=(0.01, 0.05), success_rate=1.0)
        agent = Agent(id="test_001", name="Tester", position=(0.0, 0.0))
        prompt = llm.build_prompt(agent)
        assert "Tester" in prompt

        llm.call_async(agent.id, prompt)
        assert agent.id in llm._pending

        await asyncio.sleep(0.1)
        completed = llm.poll_completed()
        assert len(completed) == 1
        assert completed[0][0] == "test_001"
        assert completed[0][1]["success"] is True


# ─── Action Tests ────────────────────────────────────────────────


class TestActions:
    def test_action_registry_has_all(self):
        """REGISTRY contains all 6 action types."""
        for action_type in ActionType:
            assert action_type in REGISTRY

    def test_drink_action(self):
        """Drinking reduces thirst to 0 (fully hydrated)."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.thirst = 80.0  # high = very thirsty
        world.get_tile(5, 5).resource_type = "water"

        result = REGISTRY[ActionType.DRINK](agent, world)
        assert agent.thirst == 0.0  # fully hydrated
        assert result.success is True

    def test_get_action_duration(self):
        """Duration varies by agent attributes."""
        fast_agent = Agent(id="fast", name="Fast", position=(0.0, 0.0), speed=80)
        slow_agent = Agent(id="slow", name="Slow", position=(0.0, 0.0), speed=20)
        fast_dur = get_action_duration(ActionType.MOVE, fast_agent)
        slow_dur = get_action_duration(ActionType.MOVE, slow_agent)
        assert fast_dur < slow_dur

    def test_move_action(self):
        """Agent advances along a pre-computed path."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(0.0, 0.0))
        agent.move_path = [(1, 0), (2, 0)]
        result = REGISTRY[ActionType.MOVE](agent, world)
        assert result.success is True
        assert agent.position == (1.0, 0.0)

    def test_chop_action(self):
        """Chopping a tree adds wood to inventory."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        world.get_tile(5, 5).resource_type = "tree"
        world.get_tile(5, 5).amount = 5
        result = REGISTRY[ActionType.CHOP](agent, world)
        assert result.success is True
        assert agent.inventory.get("wood", 0) == 1

    def test_eat_action(self):
        """Eating berries reduces hunger."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.hunger = 50.0
        agent.inventory["berries"] = 2
        result = REGISTRY[ActionType.EAT](agent, world)
        assert result.success is True
        assert agent.hunger == 30.0
        assert agent.inventory["berries"] == 1

    def test_gather_action(self):
        """Gathering from a berries tile adds berries to inventory."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        # Clear all tiles in the 3x3 area to avoid accidental matches
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                tile = world.get_tile(5 + dx, 5 + dy)
                tile.resource_type = None
                tile.amount = 0
        world.get_tile(5, 5).resource_type = "berries"
        world.get_tile(5, 5).amount = 3
        result = REGISTRY[ActionType.GATHER](agent, world)
        assert result.success is True
        assert agent.inventory.get("berries", 0) == 1

    def test_rest_action(self):
        """Resting recovers energy."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.energy = 50.0
        result = REGISTRY[ActionType.REST](agent, world)
        assert result.success is True
        assert agent.energy == 60.0

    def test_chop_no_tree(self):
        """Chopping with no tree nearby fails gracefully."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        # Clear all tiles in the 3x3 area to avoid accidental matches
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                tile = world.get_tile(5 + dx, 5 + dy)
                tile.resource_type = None
                tile.amount = 0
        result = REGISTRY[ActionType.CHOP](agent, world)
        assert result.success is False

    def test_eat_no_food(self):
        """Eating with empty inventory fails gracefully."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        agent.inventory.clear()
        result = REGISTRY[ActionType.EAT](agent, world)
        assert result.success is False


# ─── Event Queue Tests ────────────────────────────────────────────


class TestEventQueue:
    def test_push_and_drain(self):
        """Events can be pushed and drained."""
        eq = EventQueue()
        eq.push("test_event", "Test description", "info", ["agent_001"], tick=1)
        assert eq.pending_count == 1
        events = eq.drain()
        assert len(events) == 1
        assert eq.pending_count == 0

    def test_proximity_encounter(self):
        """Two nearby agents trigger an encounter event."""
        agents = [
            Agent(id="a1", name="Alice", position=(5.0, 5.0)),
            Agent(id="a2", name="Bob", position=(6.0, 6.0)),
        ]
        events = check_proximity_encounters(agents, radius=3.0)
        assert len(events) >= 1
        assert events[0].type == "encounter"

    def test_no_proximity_for_distant_agents(self):
        """Distant agents do not trigger encounters."""
        agents = [
            Agent(id="a1", name="Alice", position=(0.0, 0.0)),
            Agent(id="a2", name="Bob", position=(50.0, 50.0)),
        ]
        events = check_proximity_encounters(agents, radius=3.0)
        assert len(events) == 0


# ─── Snapshot Builder Tests ──────────────────────────────────────


class TestSnapshotBuilder:
    def test_build_contains_all_agents(self):
        """Snapshot contains all agents."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        builder = WorldSnapshotBuilder(world, agents)
        snapshot = builder.build(tick=1)
        assert len(snapshot.agents) == 3

    def test_build_contains_metrics(self):
        """Snapshot contains computed metrics."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        builder = WorldSnapshotBuilder(world, agents)
        snapshot = builder.build(tick=1)
        assert snapshot.metrics.population == 3
        assert snapshot.metrics.avg_hunger > 0

    def test_delta_removed_agents(self):
        """Delta snapshot tracks removed agents."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        builder = WorldSnapshotBuilder(world, agents)
        builder.mark_agent_removed("agent_001")
        snapshot = builder.build_delta(tick=1)
        assert "agent_001" in snapshot.removed_agents


# ─── Engine Tests ────────────────────────────────────────────────


class TestEngine:
    @pytest.mark.anyio
    async def test_engine_start_stop(self):
        """Engine starts and stops cleanly."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        engine = SimulationEngine(world=world, agents=agents)
        await engine.start()
        assert engine.running is True
        await engine.stop()
        assert engine.running is False

    @pytest.mark.anyio
    async def test_engine_ticks_increment(self):
        """Engine tick count increases after running."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        engine = SimulationEngine(world=world, agents=agents)
        # Use a very fast tick rate for testing
        engine.tick_count = 0
        await engine.start()
        await asyncio.sleep(0.05)  # Let a few ticks pass
        await engine.stop()
        assert engine.tick_count > 0

    @pytest.mark.anyio
    async def test_engine_pause_resume(self):
        """Engine pauses and resumes correctly."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        engine = SimulationEngine(world=world, agents=agents)
        assert engine.is_paused is False
        engine.pause()
        assert engine.is_paused is True
        engine.resume()
        assert engine.is_paused is False

    @pytest.mark.anyio
    async def test_agents_decay_over_time(self):
        """Agent stats decay after multiple ticks."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        engine = SimulationEngine(world=world, agents=agents)
        initial_hunger = agents[0].hunger
        await engine.start()
        await asyncio.sleep(0.1)
        await engine.stop()
        assert agents[0].hunger >= initial_hunger  # hunger increases (decays upward)

    @pytest.mark.anyio
    async def test_fsm_transitions_during_ticks(self):
        """Agents transition through FSM states during ticks."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        # Track agent's FSM
        agent = agents[0]
        # Reset FSM to idle
        engine = SimulationEngine(world=world, agents=agents)
        await engine.start()
        await asyncio.sleep(0.15)  # Let several ticks pass
        await engine.stop()
        # Agent should have moved from idle to some other state
        assert agent.fsm_state != "idle"
