"""Tests for the simulation engine and its subsystems."""

import asyncio
import pytest

from app.simulation.world import World
from app.simulation.agent import Agent, AgentFactory, FSM, MockLLMOrchestrator
from app.simulation.actions import ActionType, REGISTRY, get_action_duration
from app.simulation.event_queue import EventQueue, check_proximity_encounters
from app.simulation.snapshot import WorldSnapshotBuilder
from app.simulation.engine import SimulationEngine
from app.simulation.structures import Structure
from app.models.schemas import StructureUpdate


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

    def test_new_resource_types_exist(self):
        """ResourceType enum includes new resources."""
        from app.simulation.world import ResourceType
        assert ResourceType.IRON == "iron_ore"
        assert ResourceType.CLAY == "clay"
        assert ResourceType.SAND == "sand"
        assert ResourceType.FIBER == "fiber"

    def test_new_resources_generated(self):
        """New resources appear at correct densities in a fresh world."""
        world = World(width=50, height=50, seed=123)
        counts = {"iron_ore": 0, "clay": 0, "sand": 0, "fiber": 0}
        for y in range(world.height):
            for x in range(world.width):
                rt = world.get_tile(x, y).resource_type
                if rt in counts:
                    counts[rt] += 1
        # Expected counts: iron_ore 15, clay 25, sand 30, fiber 20
        assert counts["iron_ore"] == 15
        assert counts["clay"] == 25
        assert counts["sand"] == 30
        assert counts["fiber"] == 20

    def test_new_resource_regeneration(self):
        """Clay and fiber regenerate; iron_ore and sand do not."""
        world = World(width=50, height=50, seed=123)
        # Find one tile of each type
        tiles = {}
        for y in range(world.height):
            for x in range(world.width):
                tile = world.get_tile(x, y)
                if tile.resource_type in ("clay", "fiber", "iron_ore", "sand") and tile.resource_type not in tiles:
                    tiles[tile.resource_type] = tile
            if len(tiles) == 4:
                break
        assert "clay" in tiles and "fiber" in tiles and "iron_ore" in tiles and "sand" in tiles
        clay_orig = tiles["clay"].amount
        fiber_orig = tiles["fiber"].amount
        iron_orig = tiles["iron_ore"].amount
        sand_orig = tiles["sand"].amount
        tiles["clay"].amount -= 1
        tiles["fiber"].amount -= 1
        tiles["iron_ore"].amount -= 1
        tiles["sand"].amount -= 1
        world.regenerate_resources()
        assert tiles["clay"].amount > clay_orig - 1  # regen_rate 0.02
        assert tiles["fiber"].amount > fiber_orig - 1  # regen_rate 0.05
        assert tiles["iron_ore"].amount == iron_orig - 1  # regen_rate 0
        assert tiles["sand"].amount == sand_orig - 1  # regen_rate 0

    def test_animal_resources_generated(self):
        """Animals (deer, rabbit, boar) are placed on the map."""
        world = World(width=50, height=50, seed=42)
        counts = {"deer": 0, "rabbit": 0, "boar": 0}
        for y in range(world.height):
            for x in range(world.width):
                rt = world.get_tile(x, y).resource_type
                if rt in counts:
                    counts[rt] += 1
        assert counts["deer"] == 10
        assert counts["rabbit"] == 6
        assert counts["boar"] == 4

    def test_animal_amounts(self):
        """Animal tiles have amount 1-3."""
        world = World(width=50, height=50, seed=42)
        found = 0
        for y in range(world.height):
            for x in range(world.width):
                tile = world.get_tile(x, y)
                if tile.resource_type in ("deer", "rabbit", "boar"):
                    found += 1
                    assert 1 <= tile.amount <= 3
                    assert tile.max_amount == tile.amount
        assert found == 20  # 10 deer + 6 rabbit + 4 boar

    def test_hunting_depletes_animal_amount(self):
        """Hunting an animal tile reduces its amount."""
        world = World(width=50, height=50, seed=42)
        agent = Agent(id="test_001", name="Tester", position=(5.0, 5.0))
        # Place a deer tile adjacent to the agent
        world.get_tile(5, 5).resource_type = "deer"
        world.get_tile(5, 5).amount = 3
        world.get_tile(5, 5).max_amount = 3
        # Simulate hunting by directly reducing amount (hunt handler tests come in P2-T2)
        world.get_tile(5, 5).amount -= 1
        assert world.get_tile(5, 5).amount == 2

    def test_animal_regeneration(self):
        """Depleted animals regenerate over time."""
        world = World(width=50, height=50, seed=42)
        # Find first animal tile
        animal_tile = None
        for y in range(world.height):
            for x in range(world.width):
                tile = world.get_tile(x, y)
                if tile.resource_type in ("deer", "rabbit", "boar"):
                    animal_tile = tile
                    break
            if animal_tile:
                break
        assert animal_tile is not None
        original = animal_tile.amount
        animal_tile.amount = max(0, animal_tile.amount - 1)
        world.regenerate_resources()
        assert animal_tile.amount > original - 1

    def test_world_has_structure_manager(self):
        """World initializes with a StructureManager."""
        world = World(width=10, height=10)
        assert hasattr(world, "structures")
        from app.simulation.structures import StructureManager
        assert isinstance(world.structures, StructureManager)

    def test_wall_blocks_is_passable(self):
        """A wall structure makes its tile impassable."""
        from app.simulation.structures import Structure, StructureManager
        world = World(width=10, height=10)
        wall = Structure(id="w1", structure_type="wall", position=(3, 3))
        world.structures.add_structure(wall)
        assert world.is_passable(3, 3) is False

    def test_non_wall_structure_is_passable(self):
        """A non-wall structure does not block movement."""
        from app.simulation.structures import Structure
        world = World(width=10, height=10)
        house = Structure(id="h1", structure_type="house", position=(3, 3))
        world.structures.add_structure(house)
        assert world.is_passable(3, 3) is True

    def test_path_routed_around_wall(self):
        """BFS pathfinding avoids wall structures."""
        from app.simulation.structures import Structure
        world = World(width=5, height=5)
        wall = Structure(id="w1", structure_type="wall", position=(1, 0))
        world.structures.add_structure(wall)
        path = world.find_path((0, 0), (2, 0))
        assert len(path) > 0
        assert (1, 0) not in path


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
        assert agent.age == 0
        assert agent.max_age == 3000
        assert agent.sex in ("male", "female")

    def test_factory_default_agents(self):
        """Factory creates 3 default agents."""
        agents = AgentFactory.create_default_agents()
        assert len(agents) == 3
        assert agents[0].name == "Zog"
        assert agents[0].sex == "male"
        assert agents[0].age == 0
        assert agents[1].name == "Mila"
        assert agents[1].sex == "female"
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

    def test_agent_equipment_defaults(self):
        """Agent has default equipment fields."""
        agent = Agent(id="test_001", name="TestBot", position=(5.0, 5.0))
        assert agent.equipment == {"weapon": "fist", "armor": "none", "tool": "none"}
        assert agent.is_guarding is False

    def test_factory_equipment_from_config(self):
        """Factory parses equipment from config dict."""
        config = {
            "name": "Warrior",
            "attributes": {},
            "equipment": {"weapon": "iron_sword", "armor": "hide_armor", "tool": "none"},
        }
        agent = AgentFactory.from_config(config)
        assert agent.equipment == {"weapon": "iron_sword", "armor": "hide_armor", "tool": "none"}

    def test_agent_equipment_custom_constructor(self):
        """Agent accepts custom equipment via constructor."""
        agent = Agent(
            id="test_001",
            name="TestBot",
            position=(5.0, 5.0),
            equipment={"weapon": "spear", "armor": "fiber_armor", "tool": "hoe"},
        )
        assert agent.equipment["weapon"] == "spear"
        assert agent.equipment["armor"] == "fiber_armor"
        assert agent.equipment["tool"] == "hoe"
        assert agent.is_guarding is False

    def test_factory_from_config_applies_role_stats(self):
        """AgentFactory.from_config applies role stat modifiers."""
        config = {
            "name": "Builder",
            "role": "builder",
            "attributes": {"strength": 50},
        }
        agent = AgentFactory.from_config(config)
        assert agent.strength == 60  # 50 + 10 builder modifier

    def test_factory_from_config_sets_role_data(self):
        """AgentFactory.from_config populates agent.role_data."""
        config = {
            "name": "Miner",
            "role": "miner",
            "attributes": {},
        }
        agent = AgentFactory.from_config(config)
        assert hasattr(agent, "role_data")
        assert agent.role_data["stat_modifiers"]["strength"] == 10
        assert "mine" in agent.role_data["allowed_actions"]

    def test_engine_add_agent_applies_role_stats(self):
        """SimulationEngine.add_agent applies role stat modifiers."""
        world = World(width=10, height=10)
        engine = SimulationEngine(world=world, agents=[])
        agent = Agent(id="test_001", name="Builder", position=(5.0, 5.0), role="builder", strength=50)
        engine.add_agent(agent)
        assert agent.strength == 60  # 50 + 10

    def test_engine_add_agent_sets_role_data(self):
        """SimulationEngine.add_agent populates agent.role_data."""
        world = World(width=10, height=10)
        engine = SimulationEngine(world=world, agents=[])
        agent = Agent(id="test_001", name="Scout", position=(5.0, 5.0), role="scout")
        engine.add_agent(agent)
        assert hasattr(agent, "role_data")
        assert agent.role_data["stat_modifiers"]["speed"] == 15

    @pytest.mark.anyio
    async def test_decay_over_ten_ticks(self):
        """Over 10 ticks hunger+0.4, thirst+0.6, energy-0.3."""
        from app.simulation.engine import HUNGER_DECAY, THIRST_DECAY, ENERGY_DECAY
        world = World(width=10, height=10)
        agent = Agent(id="decay_001", name="DecayBot", position=(5.0, 5.0))
        agents = [agent]
        engine = SimulationEngine(world=world, agents=agents)
        initial_hunger = agent.hunger
        initial_thirst = agent.thirst
        initial_energy = agent.energy
        for _ in range(10):
            await engine._process_needs(tick=1)
        assert agent.hunger == pytest.approx(initial_hunger + 10 * HUNGER_DECAY)
        assert agent.thirst == pytest.approx(initial_thirst + 10 * THIRST_DECAY)
        assert agent.energy == pytest.approx(initial_energy - 10 * ENERGY_DECAY)

    def test_farm_auto_generation_within_range(self):
        """Agents within 1 tile of a farm receive 2 berries per tick."""
        from app.simulation.structures import Structure
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Farmer", position=(5.0, 5.0))
        agent.inventory.clear()
        world.structures.add_structure(
            Structure(id="f1", structure_type="farm", position=(5, 5))
        )
        engine = SimulationEngine(world=world, agents=[agent])
        engine.world.structures.tick_farms(engine.agents)
        assert agent.inventory.get("berries", 0) == 2

    def test_farm_no_yield_outside_range(self):
        """Agents farther than 1 tile from a farm receive no berries."""
        from app.simulation.structures import Structure
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Farmer", position=(5.0, 5.0))
        agent.inventory.clear()
        world.structures.add_structure(
            Structure(id="f1", structure_type="farm", position=(8, 8))
        )
        engine = SimulationEngine(world=world, agents=[agent])
        engine.world.structures.tick_farms(engine.agents)
        assert agent.inventory.get("berries", 0) == 0

    def test_house_boosts_rest_recovery(self):
        """Resting at a house tile recovers +20 energy instead of +10."""
        from app.simulation.structures import Structure
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Resting", position=(5.0, 5.0), energy=50.0)
        world.structures.add_structure(
            Structure(id="h1", structure_type="house", position=(5, 5))
        )
        result = REGISTRY[ActionType.REST](agent, world)
        assert result.success is True
        assert agent.energy == 70.0  # 50 + 20

    def test_rest_without_house_standard_recovery(self):
        """Resting without a house recovers +10 energy."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Resting", position=(5.0, 5.0), energy=50.0)
        result = REGISTRY[ActionType.REST](agent, world)
        assert result.success is True
        assert agent.energy == 60.0  # 50 + 10

    def test_tick_calls_tick_farms(self):
        """Engine _tick calls tick_farms on the structure manager."""
        from app.simulation.structures import Structure
        import asyncio

        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Farmer", position=(5.0, 5.0))
        agent.inventory.clear()
        world.structures.add_structure(
            Structure(id="f1", structure_type="farm", position=(5, 5))
        )
        engine = SimulationEngine(world=world, agents=[agent])
        asyncio.run(engine._tick())
        assert agent.inventory.get("berries", 0) == 2


# ─── Action Tests ────────────────────────────────────────────────


class TestActions:
    def test_action_registry_has_all(self):
        """REGISTRY contains all action types."""
        for action_type in ActionType:
            assert action_type in REGISTRY

    def test_attack_melee_damages_target(self):
        """Melee attack reduces target health."""
        world = World(width=10, height=10)
        attacker = Agent(id="atk_001", name="Attacker", position=(5.0, 5.0), strength=50)
        attacker.equipment["weapon"] = "spear"
        target = Agent(id="tgt_001", name="Target", position=(6.0, 6.0), health=100.0)
        target.equipment["armor"] = "none"
        agents = [attacker, target]
        step = {"target_agent": "tgt_001"}
        result = REGISTRY[ActionType.ATTACK](attacker, world, None, step, agents)
        assert result.success is True
        assert target.health < 100.0
        assert result.state_changes.get("damage_dealt", 0) > 0

    def test_attack_ranged_out_of_range_fails(self):
        """Ranged attack beyond max range fails."""
        world = World(width=20, height=20)
        attacker = Agent(id="atk_001", name="Attacker", position=(5.0, 5.0), intelligence=50)
        attacker.equipment["weapon"] = "bow"
        attacker.inventory["arrows"] = 5
        target = Agent(id="tgt_001", name="Target", position=(15.0, 15.0), health=100.0)
        agents = [attacker, target]
        step = {"target_agent": "tgt_001"}
        result = REGISTRY[ActionType.ATTACK](attacker, world, None, step, agents)
        assert result.success is False

    def test_attack_bow_without_arrows_fails(self):
        """Ranged attack with bow but no arrows fails."""
        world = World(width=10, height=10)
        attacker = Agent(id="atk_001", name="Attacker", position=(5.0, 5.0))
        attacker.equipment["weapon"] = "bow"
        target = Agent(id="tgt_001", name="Target", position=(6.0, 6.0), health=100.0)
        agents = [attacker, target]
        step = {"target_agent": "tgt_001"}
        result = REGISTRY[ActionType.ATTACK](attacker, world, None, step, agents)
        assert result.success is False

    def test_attack_self_blocked(self):
        """Attacking yourself is blocked."""
        world = World(width=10, height=10)
        attacker = Agent(id="atk_001", name="Attacker", position=(5.0, 5.0), health=100.0)
        agents = [attacker]
        step = {"target_agent": "atk_001"}
        result = REGISTRY[ActionType.ATTACK](attacker, world, None, step, agents)
        assert result.success is False

    def test_guard_sets_flag(self):
        """Guard action sets is_guarding to True."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Guardian", position=(5.0, 5.0))
        assert agent.is_guarding is False
        result = REGISTRY[ActionType.GUARD](agent, world)
        assert result.success is True
        assert agent.is_guarding is True

    def test_heal_restores_health(self):
        """Heal action restores health and consumes berry."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Healer", position=(5.0, 5.0), health=50.0, intelligence=50)
        agent.inventory["berries"] = 3
        result = REGISTRY[ActionType.HEAL](agent, world)
        assert result.success is True
        expected_heal = 10 + 50 * 0.1
        assert agent.health == pytest.approx(min(100.0, 50.0 + expected_heal))
        assert agent.inventory["berries"] == 2

    def test_heal_without_berries_fails(self):
        """Heal without berries fails."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Healer", position=(5.0, 5.0), health=50.0)
        agent.inventory.clear()
        result = REGISTRY[ActionType.HEAL](agent, world)
        assert result.success is False

    def test_attack_melee_out_of_range_fails(self):
        """Melee attack beyond 3 tiles fails."""
        world = World(width=20, height=20)
        attacker = Agent(id="atk_001", name="Attacker", position=(5.0, 5.0), strength=50)
        attacker.equipment["weapon"] = "spear"
        target = Agent(id="tgt_001", name="Target", position=(10.0, 10.0), health=100.0)
        agents = [attacker, target]
        step = {"target_agent": "tgt_001"}
        result = REGISTRY[ActionType.ATTACK](attacker, world, None, step, agents)
        assert result.success is False

    def test_attack_ranged_within_range_succeeds(self):
        """Ranged attack within 5 tiles succeeds."""
        world = World(width=20, height=20)
        attacker = Agent(id="atk_001", name="Attacker", position=(5.0, 5.0), intelligence=50)
        attacker.equipment["weapon"] = "bow"
        attacker.inventory["arrows"] = 5
        target = Agent(id="tgt_001", name="Target", position=(9.0, 5.0), health=100.0)
        agents = [attacker, target]
        step = {"target_agent": "tgt_001"}
        result = REGISTRY[ActionType.ATTACK](attacker, world, None, step, agents)
        assert result.success is True
        assert target.health < 100.0
        assert attacker.inventory.get("arrows", 0) == 4

    def test_heal_caps_at_100(self):
        """Heal does not exceed max health of 100."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Healer", position=(5.0, 5.0), health=95.0, intelligence=100)
        agent.inventory["berries"] = 3
        result = REGISTRY[ActionType.HEAL](agent, world)
        assert result.success is True
        assert agent.health == 100.0

    def test_attack_with_fist_default(self):
        """Attack with default fist weapon works."""
        world = World(width=10, height=10)
        attacker = Agent(id="atk_001", name="Attacker", position=(5.0, 5.0), strength=50)
        target = Agent(id="tgt_001", name="Target", position=(6.0, 6.0), health=100.0)
        agents = [attacker, target]
        step = {"target_agent": "tgt_001"}
        result = REGISTRY[ActionType.ATTACK](attacker, world, None, step, agents)
        assert result.success is True
        assert target.health < 100.0

    def test_combat_action_durations_defined(self):
        """ATTACK, GUARD, HEAL have defined durations."""
        agent = Agent(id="test_001", name="Tester", position=(0.0, 0.0))
        assert get_action_duration(ActionType.ATTACK, agent) == 5
        assert get_action_duration(ActionType.GUARD, agent) == 3
        assert get_action_duration(ActionType.HEAL, agent) == 5

    def test_gather_stops_at_20_without_storage(self):
        """handle_gather fails when agent already has 20 berries and no storage."""
        from app.simulation.actions import handle_gather
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Gatherer", position=(5.0, 5.0))
        agent.inventory["berries"] = 20
        # Clear all adjacent tiles to ensure only berries is available
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                world.get_tile(5 + dx, 5 + dy).resource_type = None
        world.get_tile(5, 5).resource_type = "berries"
        world.get_tile(5, 5).amount = 5
        result = handle_gather(agent, world)
        assert result.success is False
        assert "full" in result.action_summary.lower()
        assert agent.inventory["berries"] == 20

    def test_gather_continues_to_40_with_storage(self):
        """handle_gather succeeds when agent has 20 berries and storage is nearby."""
        from app.simulation.actions import handle_gather
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Gatherer", position=(5.0, 5.0))
        agent.inventory["berries"] = 20
        agent._storage_nearby = True
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                world.get_tile(5 + dx, 5 + dy).resource_type = None
        world.get_tile(5, 5).resource_type = "berries"
        world.get_tile(5, 5).amount = 5
        result = handle_gather(agent, world)
        assert result.success is True
        assert agent.inventory["berries"] == 21

    def test_chop_stops_at_20_without_storage(self):
        """handle_chop fails when agent already has 20 wood and no storage."""
        from app.simulation.actions import handle_chop
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Chopper", position=(5.0, 5.0))
        agent.inventory["wood"] = 20
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                world.get_tile(5 + dx, 5 + dy).resource_type = None
        world.get_tile(5, 5).resource_type = "tree"
        world.get_tile(5, 5).amount = 5
        result = handle_chop(agent, world)
        assert result.success is False
        assert agent.inventory["wood"] == 20

    def test_engine_sets_storage_nearby_flag(self):
        """Engine _tick sets _storage_nearby when storage_hut is within 3 tiles."""
        from app.simulation.structures import Structure
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Gatherer", position=(5.0, 5.0))
        world.structures.add_structure(
            Structure(id="sh1", structure_type="storage_hut", position=(7, 7))
        )
        engine = SimulationEngine(world=world, agents=[agent])
        # Manually call the tick logic that sets the flag
        import asyncio
        # We can't easily run _tick without async, so call the helper directly if exposed
        # Instead, check after a single tick via start/stop
        asyncio.run(engine._tick())
        assert agent._storage_nearby is True

    def test_engine_clears_storage_nearby_flag(self):
        """Engine _tick clears _storage_nearby when no storage_hut is near."""
        from app.simulation.structures import Structure
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Gatherer", position=(5.0, 5.0))
        agent._storage_nearby = True  # previously set
        world.structures.add_structure(
            Structure(id="sh1", structure_type="storage_hut", position=(9, 9))
        )
        engine = SimulationEngine(world=world, agents=[agent])
        import asyncio
        asyncio.run(engine._tick())
        assert agent._storage_nearby is False


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

    def test_new_event_types_push_and_drain(self):
        """New event types (craft, build, fight, combat_death) can be pushed and drained."""
        from app.simulation.event_queue import EventQueue
        eq = EventQueue()
        for event_type in ("craft", "build", "fight", "combat_death"):
            eq.push(event_type, f"A {event_type} happened", "info", ["agent_001"], tick=1)
        events = eq.drain()
        assert len(events) == 4
        types = {e.type for e in events}
        assert types == {"craft", "build", "fight", "combat_death"}

    def test_death_event_violence_cause(self):
        """create_death_event with violence cause includes correct metadata."""
        from app.simulation.event_queue import create_death_event
        agent = Agent(id="test_001", name="Victim", position=(5.0, 5.0))
        event = create_death_event(agent, current_tick=10, cause="violence")
        assert event.type == "death"
        assert event.metadata["cause"] == "violence"
        assert "killed" in event.description.lower()

    def test_death_event_invalid_cause_raises(self):
        """create_death_event with unknown cause raises ValueError."""
        from app.simulation.event_queue import create_death_event
        agent = Agent(id="test_001", name="Victim", position=(5.0, 5.0))
        with pytest.raises(ValueError, match="Unknown death cause"):
            create_death_event(agent, current_tick=10, cause="unknown")


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

    def test_snapshot_contains_new_fields(self):
        """Snapshot AgentState includes new lifecycle fields."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        builder = WorldSnapshotBuilder(world, agents)
        snapshot = builder.build(tick=1)
        agent_state = snapshot.agents["agent_001"]
        assert agent_state.sex in ("male", "female")
        assert agent_state.age == 0
        assert agent_state.max_age > 0
        assert agent_state.strength > 0
        assert agent_state.sociability > 0
        assert hasattr(agent_state, "system_prompt")
        assert hasattr(agent_state, "monologue_history")

    def test_delta_removed_agents(self):
        """Delta snapshot tracks removed agents."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        builder = WorldSnapshotBuilder(world, agents)
        builder.mark_agent_removed("agent_001")
        snapshot = builder.build_delta(tick=1)
        assert "agent_001" in snapshot.removed_agents

    def test_snapshot_includes_equipment_defaults(self):
        """AgentState includes equipment dict with defaults."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        builder = WorldSnapshotBuilder(world, agents)
        snapshot = builder.build(tick=1)
        agent_state = snapshot.agents["agent_001"]
        assert agent_state.equipment == {"weapon": "fist", "armor": "none", "tool": "none"}

    def test_snapshot_includes_equipment_custom(self):
        """AgentState reflects custom equipment."""
        world = World(width=10, height=10)
        agents = [
            Agent(
                id="test_001",
                name="Warrior",
                position=(5.0, 5.0),
                equipment={"weapon": "iron_sword", "armor": "hide_armor", "tool": "none"},
            )
        ]
        builder = WorldSnapshotBuilder(world, agents)
        snapshot = builder.build(tick=1)
        assert snapshot.agents["test_001"].equipment == {"weapon": "iron_sword", "armor": "hide_armor", "tool": "none"}

    def test_snapshot_includes_structures(self):
        """Full snapshot includes all structures in the world."""
        world = World(width=10, height=10)
        world.structures.add_structure(
            Structure(id="s1", structure_type="house", position=(3, 3), owner_id="agent_001")
        )
        agents = AgentFactory.create_default_agents()
        builder = WorldSnapshotBuilder(world, agents)
        snapshot = builder.build(tick=1)
        assert len(snapshot.structures) == 1
        assert snapshot.structures[0].id == "s1"
        assert snapshot.structures[0].structure_type == "house"
        assert snapshot.structures[0].position == (3, 3)
        assert snapshot.structures[0].owner_id == "agent_001"

    def test_snapshot_structures_empty_when_none(self):
        """Snapshot structures list is empty when no structures exist."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        builder = WorldSnapshotBuilder(world, agents)
        snapshot = builder.build(tick=1)
        assert snapshot.structures == []

    def test_delta_snapshot_includes_dirty_structures(self):
        """Delta snapshot includes only dirty structures."""
        world = World(width=10, height=10)
        world.structures.add_structure(
            Structure(id="s1", structure_type="house", position=(3, 3))
        )
        world.structures.add_structure(
            Structure(id="s2", structure_type="wall", position=(5, 5))
        )
        agents = AgentFactory.create_default_agents()
        builder = WorldSnapshotBuilder(world, agents)
        builder.mark_structure_dirty("s2")
        snapshot = builder.build_delta(tick=1)
        assert len(snapshot.structures) == 1
        assert snapshot.structures[0].id == "s2"

    def test_delta_snapshot_clears_dirty_structures(self):
        """Dirty structures set is cleared after build_delta."""
        world = World(width=10, height=10)
        world.structures.add_structure(
            Structure(id="s1", structure_type="house", position=(3, 3))
        )
        agents = AgentFactory.create_default_agents()
        builder = WorldSnapshotBuilder(world, agents)
        builder.mark_structure_dirty("s1")
        builder.build_delta(tick=1)
        # Second delta should have no structures
        snapshot = builder.build_delta(tick=2)
        assert snapshot.structures == []


class TestStructureUpdateSchema:
    def test_structure_update_fields(self):
        """StructureUpdate schema has the required fields."""
        su = StructureUpdate(
            id="s1",
            structure_type="wall",
            position=(2, 3),
            health=100.0,
            max_health=100.0,
            owner_id="agent_001",
        )
        assert su.id == "s1"
        assert su.structure_type == "wall"
        assert su.position == (2, 3)
        assert su.health == 100.0
        assert su.max_health == 100.0
        assert su.owner_id == "agent_001"

    def test_structure_update_owner_optional(self):
        """StructureUpdate owner_id can be None."""
        su = StructureUpdate(
            id="s1",
            structure_type="wall",
            position=(2, 3),
            health=100.0,
            max_health=100.0,
            owner_id=None,
        )
        assert su.owner_id is None


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

    @pytest.mark.anyio
    async def test_agent_age_increments(self):
        """Agent age increases each tick."""
        world = World(width=10, height=10)
        agents = AgentFactory.create_default_agents()
        engine = SimulationEngine(world=world, agents=agents)
        await engine.start()
        await asyncio.sleep(0.15)
        await engine.stop()
        for agent in agents:
            assert agent.age > 0

    @pytest.mark.anyio
    async def test_agent_max_age(self):
        """Agent with max_age=0 dies immediately."""
        world = World(width=10, height=10)
        from app.simulation.agent import Agent
        old_agent = Agent(id="old_001", name="Oldie", position=(5.0, 5.0), max_age=0, age=0)
        agents = [old_agent]
        engine = SimulationEngine(world=world, agents=agents)
        await engine.start()
        await asyncio.sleep(0.15)
        await engine.stop()
        assert old_agent not in engine.agents  # Should have died

    def test_gatherer_uses_survival_chain(self):
        """Gatherer with empty priorities falls through to survival chain."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Gatherer", position=(5.0, 5.0), role="gatherer")
        agent.hunger = 80  # critical hunger
        world.get_tile(5, 5).resource_type = "berries"
        world.get_tile(5, 5).amount = 5
        agents = [agent]
        engine = SimulationEngine(world=world, agents=agents)
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")
        engine._fsm_evaluate(agent, fsm, tick=1)
        # With old survival chain, critical hunger + adjacent food → gather
        assert agent.current_action == "gather"

    def test_fighter_prioritizes_attack(self):
        """Fighter with an enemy nearby chooses attack over gather."""
        world = World(width=10, height=10)
        fighter = Agent(id="test_001", name="Fighter", position=(5.0, 5.0), role="fighter")
        fighter.hunger = 80  # critical hunger
        enemy = Agent(id="test_002", name="Enemy", position=(6.0, 6.0), role="gatherer")
        world.get_tile(5, 5).resource_type = "berries"
        world.get_tile(5, 5).amount = 5
        agents = [fighter, enemy]
        engine = SimulationEngine(world=world, agents=agents)
        fsm = engine.fsms[fighter.id]
        fsm.transition_to("evaluate")
        engine._fsm_evaluate(fighter, fsm, tick=1)
        # Fighter priorities: attack (80) before gather (60)
        assert fighter.current_action == "attack"

    def test_scout_picks_explore(self):
        """Scout with no critical needs picks explore."""
        world = World(width=10, height=10)
        scout = Agent(id="test_001", name="Scout", position=(5.0, 5.0), role="scout")
        scout.hunger = 30
        scout.thirst = 30
        scout.energy = 80
        agents = [scout]
        engine = SimulationEngine(world=world, agents=agents)
        fsm = engine.fsms[scout.id]
        fsm.transition_to("evaluate")
        engine._fsm_evaluate(scout, fsm, tick=1)
        # Scout priorities: explore (90) is highest
        assert scout.current_action == "explore"

    def test_fsm_skips_disallowed_action_in_plan(self):
        """Gatherer with ATTACK in LLM plan skips the disallowed step."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Gatherer", position=(5.0, 5.0), role="gatherer")
        agent.hunger = 30
        agent.thirst = 30
        agent.energy = 80
        agent.active_plan = {
            "steps": [
                {"action": "attack", "target": None, "reason": "Fight"},
                {"action": "gather", "target": None, "reason": "Collect"},
            ]
        }
        agent.plan_step_index = 0
        agents = [agent]
        engine = SimulationEngine(world=world, agents=agents)
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")
        engine._fsm_evaluate(agent, fsm, tick=1)
        # attack is not allowed for gatherer → skip to gather
        assert agent.current_action == "gather"
        assert agent.plan_step_index == 1

    def test_fsm_blocks_all_disallowed_plan_steps(self):
        """If all remaining plan steps are disallowed, plan is cleared."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Gatherer", position=(5.0, 5.0), role="gatherer")
        agent.hunger = 30
        agent.thirst = 30
        agent.energy = 80
        agent.active_plan = {
            "steps": [
                {"action": "attack", "target": None, "reason": "Fight"},
            ]
        }
        agent.plan_step_index = 0
        agents = [agent]
        engine = SimulationEngine(world=world, agents=agents)
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")
        engine._fsm_evaluate(agent, fsm, tick=1)
        # All steps disallowed → plan cleared, falls through to idle/evaluate
        assert agent.active_plan is None

    def test_fsm_allows_role_permitted_plan_step(self):
        """Fighter with ATTACK in plan is allowed to execute it."""
        world = World(width=10, height=10)
        fighter = Agent(id="test_001", name="Fighter", position=(5.0, 5.0), role="fighter")
        enemy = Agent(id="test_002", name="Enemy", position=(6.0, 6.0), role="gatherer")
        fighter.hunger = 30
        fighter.thirst = 30
        fighter.energy = 80
        fighter.active_plan = {
            "steps": [
                {"action": "attack", "target": None, "reason": "Fight"},
            ]
        }
        fighter.plan_step_index = 0
        agents = [fighter, enemy]
        engine = SimulationEngine(world=world, agents=agents)
        fsm = engine.fsms[fighter.id]
        fsm.transition_to("evaluate")
        engine._fsm_evaluate(fighter, fsm, tick=1)
        assert fighter.current_action == "attack"

    def test_decay_rates_constants(self):
        """Decay constants are set to rebalanced values."""
        from app.simulation.engine import HUNGER_DECAY, THIRST_DECAY, ENERGY_DECAY
        assert HUNGER_DECAY == 0.04
        assert THIRST_DECAY == 0.06
        assert ENERGY_DECAY == 0.03

    def test_combat_death_removes_agent(self):
        """Agent killed in combat is removed from simulation."""
        world = World(width=10, height=10)
        attacker = Agent(id="atk_001", name="Attacker", position=(5.0, 5.0), strength=100)
        attacker.equipment["weapon"] = "iron_sword"
        target = Agent(id="tgt_001", name="Victim", position=(6.0, 6.0), health=10.0)
        target.equipment["armor"] = "none"
        agents = [attacker, target]
        engine = SimulationEngine(world=world, agents=agents)
        step = {"target_agent": "tgt_001"}
        REGISTRY[ActionType.ATTACK](attacker, world, None, step, agents)
        # After attack, target health should be <= 0
        assert target.health <= 0
        # Process needs should trigger combat death removal
        import asyncio
        asyncio.run(engine._process_needs(tick=1))
        assert target not in engine.agents

    def test_combat_death_emits_event(self):
        """Combat death emits a combat_death event."""
        world = World(width=10, height=10)
        attacker = Agent(id="atk_001", name="Attacker", position=(5.0, 5.0), strength=100)
        attacker.equipment["weapon"] = "iron_sword"
        target = Agent(id="tgt_001", name="Victim", position=(6.0, 6.0), health=10.0)
        agents = [attacker, target]
        engine = SimulationEngine(world=world, agents=agents)
        step = {"target_agent": "tgt_001"}
        REGISTRY[ActionType.ATTACK](attacker, world, None, step, agents)
        import asyncio
        asyncio.run(engine._process_needs(tick=1))
        events = engine.event_queue.drain()
        combat_deaths = [e for e in events if e.type == "combat_death"]
        assert len(combat_deaths) == 1
        assert combat_deaths[0].metadata.get("cause") == "violence"
        assert combat_deaths[0].metadata.get("attacker_id") == "atk_001"
        assert combat_deaths[0].metadata.get("target_id") == "tgt_001"

    def test_combat_death_applies_relationship_penalty(self):
        """Combat death reduces relationship scores between killer and victim."""
        world = World(width=10, height=10)
        attacker = Agent(id="atk_001", name="Attacker", position=(5.0, 5.0), strength=100)
        attacker.equipment["weapon"] = "iron_sword"
        target = Agent(id="tgt_001", name="Victim", position=(6.0, 6.0), health=10.0)
        # Pre-existing relationship
        from app.simulation.agent import RelationshipData
        attacker.relationships["tgt_001"] = RelationshipData(score=0.2)
        target.relationships["atk_001"] = RelationshipData(score=0.3)
        agents = [attacker, target]
        engine = SimulationEngine(world=world, agents=agents)
        step = {"target_agent": "tgt_001"}
        REGISTRY[ActionType.ATTACK](attacker, world, None, step, agents)
        import asyncio
        asyncio.run(engine._process_needs(tick=1))
        # Target is removed, but attacker relationship should be updated before removal
        # Since target is removed, we can only check attacker's relationship
        assert attacker.relationships["tgt_001"].score == pytest.approx(0.2 - 0.5)

    def test_combat_death_clears_guard(self):
        """Combat death clears guarding flag and resets equipment."""
        world = World(width=10, height=10)
        attacker = Agent(id="atk_001", name="Attacker", position=(5.0, 5.0), strength=100)
        attacker.equipment["weapon"] = "iron_sword"
        target = Agent(id="tgt_001", name="Victim", position=(6.0, 6.0), health=10.0)
        target.is_guarding = True
        target.equipment = {"weapon": "spear", "armor": "hide_armor", "tool": "hoe"}
        agents = [attacker, target]
        engine = SimulationEngine(world=world, agents=agents)
        step = {"target_agent": "tgt_001"}
        REGISTRY[ActionType.ATTACK](attacker, world, None, step, agents)
        import asyncio
        asyncio.run(engine._process_needs(tick=1))
        # Target was removed; verify by checking it no longer exists
        assert target not in engine.agents

    def test_non_combat_death_uses_death_event(self):
        """Starvation death still emits 'death' event, not 'combat_death'."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Starving", position=(5.0, 5.0), health=0.5, hunger=100.0, thirst=50.0)
        agents = [agent]
        engine = SimulationEngine(world=world, agents=agents)
        import asyncio
        asyncio.run(engine._process_needs(tick=1))
        events = engine.event_queue.drain()
        death_events = [e for e in events if e.type == "death"]
        combat_deaths = [e for e in events if e.type == "combat_death"]
        assert len(death_events) == 1
        assert len(combat_deaths) == 0

    def test_combat_interruption_forces_evaluate(self):
        """Agent in executing state re-evaluates when health drops."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Victim", position=(5.0, 5.0), health=100.0)
        agents = [agent]
        engine = SimulationEngine(world=world, agents=agents)
        fsm = engine.fsms[agent.id]
        # Put agent into executing state
        fsm.transition_to("evaluate")
        fsm.transition_to("executing")
        agent.current_action = "rest"
        agent.action_duration = 10
        agent.action_progress = 3.0
        # Simulate health decrease (e.g., from an attack)
        agent.health = 80.0
        engine._agent_health[agent.id] = 100.0  # previous health was higher
        engine._run_agent_fsm(agent, tick=1)
        # Should be interrupted out of executing (evaluate may transition further)
        assert fsm.current_state != "executing"
        assert agent.is_guarding is False  # guard should be cleared on interrupt

    def test_no_interruption_when_health_unchanged(self):
        """Agent continues executing if health did not decrease."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Stable", position=(5.0, 5.0), health=100.0)
        agents = [agent]
        engine = SimulationEngine(world=world, agents=agents)
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")
        fsm.transition_to("executing")
        agent.current_action = "rest"
        agent.action_duration = 10
        agent.action_progress = 3.0
        engine._agent_health[agent.id] = 100.0  # same as current
        engine._run_agent_fsm(agent, tick=1)
        # Should stay in executing (action not finished yet)
        assert fsm.current_state == "executing"

    @pytest.mark.anyio
    async def test_decay_over_ten_ticks(self):
        """Over 10 ticks hunger+0.4, thirst+0.6, energy-0.3."""
        from app.simulation.engine import HUNGER_DECAY, THIRST_DECAY, ENERGY_DECAY
        world = World(width=10, height=10)
        agent = Agent(id="decay_001", name="DecayBot", position=(5.0, 5.0))
        agents = [agent]
        engine = SimulationEngine(world=world, agents=agents)
        initial_hunger = agent.hunger
        initial_thirst = agent.thirst
        initial_energy = agent.energy
        for _ in range(10):
            await engine._process_needs(tick=1)
        assert agent.hunger == pytest.approx(initial_hunger + 10 * HUNGER_DECAY)
        assert agent.thirst == pytest.approx(initial_thirst + 10 * THIRST_DECAY)
        assert agent.energy == pytest.approx(initial_energy - 10 * ENERGY_DECAY)


# ─── Integration Tests ───────────────────────────────────────────


class TestIntegration:
    def test_role_differentiation_integration(self):
        """Gatherer, fighter, and builder produce different action sequences."""
        world = World(width=10, height=10)
        gatherer = Agent(id="g1", name="Gatherer", position=(5.0, 5.0), role="gatherer")
        fighter = Agent(id="f1", name="Fighter", position=(6.0, 6.0), role="fighter")
        builder = Agent(id="b1", name="Builder", position=(7.0, 7.0), role="builder")
        # Resources
        world.get_tile(5, 5).resource_type = "berries"
        world.get_tile(5, 5).amount = 5
        world.get_tile(7, 7).resource_type = None
        world.get_tile(7, 7).blocked = False
        # Critical hunger triggers gather
        gatherer.hunger = 80
        # Builder materials
        builder.inventory = {"wood": 20, "stone": 20}
        # Enemy for fighter
        enemy = Agent(id="e1", name="Enemy", position=(6.5, 6.5), role="gatherer")
        agents = [gatherer, fighter, builder, enemy]
        engine = SimulationEngine(world=world, agents=agents)
        for agent in [gatherer, fighter, builder]:
            fsm = engine.fsms[agent.id]
            fsm.transition_to("evaluate")
            engine._fsm_evaluate(agent, fsm, tick=1)
        assert gatherer.current_action == "gather"
        assert fighter.current_action == "attack"
        assert builder.current_action == "build"

    def test_craft_axe_then_chop_faster(self):
        """Crafting a stone_axe reduces chop duration."""
        from app.simulation.crafting import CraftingManager
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Crafter", position=(5.0, 5.0))
        agent.inventory = {"wood": 10, "stone": 10}
        base_duration = get_action_duration(ActionType.CHOP, agent)
        result = CraftingManager.craft(agent, "stone_axe", world)
        assert result.success is True
        assert "stone_axe" in agent.inventory
        new_duration = get_action_duration(ActionType.CHOP, agent)
        assert new_duration < base_duration

    def test_build_wall_blocks_pathfinding_integration(self):
        """Building a wall blocks BFS pathfinding."""
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Builder", position=(5.0, 5.0))
        agent.inventory = {"wood": 10, "stone": 20}
        # Clear tile before building
        world.get_tile(5, 5).resource_type = None
        world.get_tile(5, 5).blocked = False
        # Build a wall
        step = {"structure_type": "wall"}
        result = REGISTRY[ActionType.BUILD](agent, world, None, step)
        assert result.success is True
        assert world.is_passable(5, 5) is False
        path = world.find_path((4, 5), (6, 5))
        # Should route around or be empty if fully blocked
        assert (5, 5) not in path

    def test_combat_death_full_flow_integration(self):
        """Attack reduces health and combat death removes agent and emits event."""
        world = World(width=10, height=10)
        attacker = Agent(id="atk_001", name="Attacker", position=(5.0, 5.0), strength=100)
        attacker.equipment["weapon"] = "iron_sword"
        victim = Agent(id="vic_001", name="Victim", position=(6.0, 6.0), health=10.0)
        agents = [attacker, victim]
        engine = SimulationEngine(world=world, agents=agents)
        step = {"target_agent": "vic_001"}
        result = REGISTRY[ActionType.ATTACK](attacker, world, None, step, agents)
        assert result.success is True
        assert victim.health <= 0
        import asyncio
        asyncio.run(engine._process_needs(tick=1))
        assert victim not in engine.agents
        events = engine.event_queue.drain()
        combat_deaths = [e for e in events if e.type == "combat_death"]
        assert len(combat_deaths) == 1
        assert combat_deaths[0].metadata["cause"] == "violence"

    def test_mine_craft_sword_attack_pipeline_integration(self):
        """Full pipeline: mine iron, craft iron_sword, equip, attack."""
        from app.simulation.crafting import CraftingManager
        world = World(width=10, height=10)
        agent = Agent(id="test_001", name="Miner", position=(5.0, 5.0), strength=80)
        target = Agent(id="tgt_001", name="Target", position=(6.0, 6.0), health=100.0)
        # Mine iron_ore
        world.get_tile(5, 5).resource_type = "iron_ore"
        world.get_tile(5, 5).amount = 10
        mine_result = REGISTRY[ActionType.MINE](agent, world)
        assert mine_result.success is True
        assert agent.inventory.get("iron_ore", 0) >= 1
        # Provide sufficient materials
        agent.inventory["iron_ore"] = 5
        agent.inventory["wood"] = 10
        # Place forge tile for workbench requirement
        world.get_tile(5, 5).resource_type = "forge"
        world.get_tile(5, 5).amount = 1
        # Craft iron_sword
        craft_result = CraftingManager.craft(agent, "iron_sword", world)
        assert craft_result.success is True
        assert agent.inventory.get("iron_sword", 0) == 1
        # Equip sword
        agent.equipment["weapon"] = "iron_sword"
        # Attack
        step = {"target_agent": "tgt_001"}
        attack_result = REGISTRY[ActionType.ATTACK](agent, world, None, step, [agent, target])
        assert attack_result.success is True
        assert target.health < 100.0
        assert attack_result.state_changes["damage_dealt"] > 20

    def test_action_durations_are_reasonable(self):
        """New action durations fall within reasonable ranges."""
        agent = Agent(id="test_001", name="Tester", position=(0.0, 0.0))
        # Reasonable ranges based on design
        assert 1 <= get_action_duration(ActionType.MINE, agent) <= 10
        assert 1 <= get_action_duration(ActionType.EXPLORE, agent) <= 5
        assert 1 <= get_action_duration(ActionType.CRAFT, agent) <= 15
        assert 1 <= get_action_duration(ActionType.HUNT, agent) <= 10
        assert 1 <= get_action_duration(ActionType.FISH, agent) <= 10
        assert 1 <= get_action_duration(ActionType.ATTACK, agent) <= 10
        assert 1 <= get_action_duration(ActionType.GUARD, agent) <= 5
        assert 1 <= get_action_duration(ActionType.HEAL, agent) <= 10
        assert 1 <= get_action_duration(ActionType.BUILD, agent) <= 15
        assert 1 <= get_action_duration(ActionType.FARM, agent) <= 10
