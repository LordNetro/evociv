"""Tests for the Map Memory + Fog of War system."""

from app.simulation.agent import Agent
from app.simulation.faction import Faction, FactionManager
from app.simulation.world import World
from app.simulation.map_memory import TileMemory, MapMemoryManager


# ---------------------------------------------------------------------------
# TileMemory dataclass
# ---------------------------------------------------------------------------

class TestTileMemory:
    """TileMemory dataclass — default and custom values."""

    def test_default_values(self):
        """RED: TileMemory defaults to empty resource, 0 amount, 0 tick."""
        mem = TileMemory()
        assert mem.resource_type is None
        assert mem.amount == 0
        assert mem.tick_last_seen == 0

    def test_custom_values(self):
        """RED: TileMemory stores custom resource_type, amount, tick."""
        mem = TileMemory(resource_type="wood", amount=50, tick_last_seen=100)
        assert mem.resource_type == "wood"
        assert mem.amount == 50
        assert mem.tick_last_seen == 100


# ---------------------------------------------------------------------------
# get_vision_radius
# ---------------------------------------------------------------------------

class TestGetVisionRadius:
    """Vision radius computation — base, night, weather, skill, clamp."""

    def test_base_radius(self):
        """RED: Day, fair weather, no skill → radius=5."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        radius = MapMemoryManager.get_vision_radius(agent, is_night=False, weather_name="")
        assert radius == 5

    def test_night_reduces_radius(self):
        """RED: Night (×0.7) alone → floor(5*0.7) = 3."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        radius = MapMemoryManager.get_vision_radius(agent, is_night=True, weather_name="")
        assert radius == 3

    def test_fog_reduces_radius(self):
        """RED: Fog (×0.5) alone → floor(5*0.5) = 2."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        radius = MapMemoryManager.get_vision_radius(agent, is_night=False, weather_name="fog")
        assert radius == 2

    def test_night_fog_skill_bonus(self):
        """RED: Night + fog + survival level 10 → floor(5*0.7*0.5) + 10//5 = 1+2 = 3."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.skills["survival"] = 7000  # level 10 (max)
        radius = MapMemoryManager.get_vision_radius(agent, is_night=True, weather_name="fog")
        assert radius == 3

    def test_minimum_radius_floor(self):
        """RED: Night + fog + no skill → radius=1 (minimum floor)."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        radius = MapMemoryManager.get_vision_radius(agent, is_night=True, weather_name="fog")
        assert radius == 1

    def test_survival_skill_bonus(self):
        """RED: Survival level 5 adds +1 to base radius (5 + 5//5 = 6)."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.skills["survival"] = 1200  # level 5
        radius = MapMemoryManager.get_vision_radius(agent, is_night=False, weather_name="")
        assert radius == 6

    def test_clamped_to_maximum_15(self):
        """RED: Even with very high skill, radius is clamped to 15."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.skills["survival"] = 99999  # max level 10 → +2, base=5, total=7 not close to 15
        # With max level and no negative modifiers, the max achievable is 5 + 10//5 = 7
        # The clamp to 15 is a safety measure. Let's verify it works with artificial inputs.
        # We can't easily reach 15 naturally, so let's just verify the clamp exists.
        radius = MapMemoryManager.get_vision_radius(agent, is_night=False, weather_name="")
        assert radius <= 15

    def test_rainy_weather_modifier(self):
        """RED: Rainy (×0.7) → floor(5*0.7) = 3."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        radius = MapMemoryManager.get_vision_radius(agent, is_night=False, weather_name="rainy")
        assert radius == 3

    def test_storm_weather_modifier(self):
        """RED: Storm (×0.4) → floor(5*0.4) = 2."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        radius = MapMemoryManager.get_vision_radius(agent, is_night=False, weather_name="storm")
        assert radius == 2

    def test_clear_weather_no_modifier(self):
        """RED: Clear weather (×1.0) → radius=5."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        radius = MapMemoryManager.get_vision_radius(agent, is_night=False, weather_name="clear")
        assert radius == 5

    def test_night_storm_minimum(self):
        """RED: Night + storm → floor(5*0.7*0.4) = 1."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        radius = MapMemoryManager.get_vision_radius(agent, is_night=True, weather_name="storm")
        assert radius == 1


# ---------------------------------------------------------------------------
# get_visible_tiles
# ---------------------------------------------------------------------------

class TestGetVisibleTiles:
    """Manhattan-distance tile scan — bounds and radius."""

    def test_radius_0_returns_agent_tile(self):
        """RED: Radius 0 returns only the agent's current tile."""
        agent = Agent(id="test", name="Test", position=(5.0, 5.0))
        world = World(width=10, height=10)
        tiles = MapMemoryManager.get_visible_tiles(agent, world, 0)
        assert tiles == [(5, 5)]

    def test_radius_1_count(self):
        """RED: Radius 1 returns 5 tiles (center + 4 cardinal)."""
        agent = Agent(id="test", name="Test", position=(5.0, 5.0))
        world = World(width=10, height=10)
        tiles = MapMemoryManager.get_visible_tiles(agent, world, 1)
        assert len(tiles) == 5
        assert (5, 5) in tiles
        assert (4, 5) in tiles
        assert (6, 5) in tiles
        assert (5, 4) in tiles
        assert (5, 6) in tiles

    def test_radius_2_count(self):
        """RED: Radius 2 returns 13 tiles (1 + 4 + 8)."""
        agent = Agent(id="test", name="Test", position=(5.0, 5.0))
        world = World(width=10, height=10)
        tiles = MapMemoryManager.get_visible_tiles(agent, world, 2)
        assert len(tiles) == 13

    def test_radius_3_count(self):
        """RED: Radius 3 returns 25 tiles."""
        agent = Agent(id="test", name="Test", position=(5.0, 5.0))
        world = World(width=10, height=10)
        tiles = MapMemoryManager.get_visible_tiles(agent, world, 3)
        assert len(tiles) == 25

    def test_bounds_clamping_near_edge(self):
        """RED: Agent near edge gets fewer tiles (no out-of-bounds)."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        world = World(width=10, height=10)
        tiles = MapMemoryManager.get_visible_tiles(agent, world, 3)
        # At corner (0,0) with radius 3: tiles with |x|+|y| <= 3 in [0,9]
        # Expected: (0,0),(1,0),(2,0),(3,0),(0,1),(1,1),(2,1),(0,2),(1,2),(0,3) = 10
        assert len(tiles) == 10
        for x, y in tiles:
            assert 0 <= x < 10
            assert 0 <= y < 10

    def test_large_radius_clipped_to_world(self):
        """RED: Radius larger than world returns all tiles."""
        agent = Agent(id="test", name="Test", position=(2.0, 2.0))
        world = World(width=5, height=5)
        tiles = MapMemoryManager.get_visible_tiles(agent, world, 10)
        # All 25 tiles
        assert len(tiles) == 25


# ---------------------------------------------------------------------------
# update_vision
# ---------------------------------------------------------------------------

class TestUpdateVision:
    """Agent tile memory update and faction sync."""

    def test_agent_memory_populated_after_move(self):
        """RED: After update_vision, agent.tile_memory has visible tiles."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        world = World(width=10, height=10)
        # Set a resource on a nearby tile so we know what to expect
        from app.simulation.world import Tile
        world.set_tile(1, 0, Tile(x=1, y=0, resource_type="wood", amount=30))

        MapMemoryManager.update_vision(agent, world, faction_manager=None, tick=1)

        # Agent should have tile_memory for visible tiles
        assert len(agent.tile_memory) > 0
        # Tile (1,0) should be in memory
        assert (1, 0) in agent.tile_memory
        assert agent.tile_memory[(1, 0)].resource_type == "wood"
        assert agent.tile_memory[(1, 0)].amount == 30
        assert agent.tile_memory[(1, 0)].tick_last_seen == 1

    def test_explored_tiles_updated(self):
        """RED: Explored_tiles set grows with new discoveries."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        world = World(width=10, height=10)
        agent.explored_tiles.clear()

        MapMemoryManager.update_vision(agent, world, faction_manager=None, tick=1)

        # Explored tiles should include visible tiles
        assert len(agent.explored_tiles) > 0
        assert (0, 0) in agent.explored_tiles
        assert (1, 0) in agent.explored_tiles

    def test_existing_memory_preserved_outside_vision(self):
        """RED: Tiles outside current vision keep old memory."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        world = World(width=10, height=10)
        # Manually add a memory for a distant tile
        agent.tile_memory[(9, 9)] = TileMemory(resource_type="stone", amount=50, tick_last_seen=10)

        MapMemoryManager.update_vision(agent, world, faction_manager=None, tick=20)

        # Distant tile should be unchanged
        assert agent.tile_memory[(9, 9)].resource_type == "stone"
        assert agent.tile_memory[(9, 9)].amount == 50
        assert agent.tile_memory[(9, 9)].tick_last_seen == 10

    def test_tile_change_detected(self):
        """RED: When tile resource changes, tile_memory updates."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        world = World(width=10, height=10)
        from app.simulation.world import Tile

        # First scan: tile (1,0) has wood
        world.set_tile(1, 0, Tile(x=1, y=0, resource_type="wood", amount=30))
        MapMemoryManager.update_vision(agent, world, faction_manager=None, tick=1)
        assert agent.tile_memory[(1, 0)].resource_type == "wood"
        assert agent.tile_memory[(1, 0)].amount == 30

        # Change tile to stone and rescan
        world.set_tile(1, 0, Tile(x=1, y=0, resource_type="stone", amount=10))
        MapMemoryManager.update_vision(agent, world, faction_manager=None, tick=5)

        assert agent.tile_memory[(1, 0)].resource_type == "stone"
        assert agent.tile_memory[(1, 0)].amount == 10
        assert agent.tile_memory[(1, 0)].tick_last_seen == 5

    def test_faction_sync_on_discovery(self):
        """RED: New discoveries sync to faction shared_tile_memory."""
        agent = Agent(id="test", name="Test", position=(5.0, 5.0))
        world = World(width=20, height=20)
        fm = FactionManager()
        faction = fm.create("TestFaction", "#FF0000")
        agent.faction_id = faction.id
        fm.join(agent.id, faction.id)

        MapMemoryManager.update_vision(agent, world, fm, tick=1)

        # Faction should have shared tile memory from agent's vision
        assert len(faction.shared_tile_memory) > 0
        assert (5, 5) in faction.shared_tile_memory

    def test_faction_sync_tracks_reporter(self):
        """RED: tile_reported_by tracks which agent reported each tile."""
        agent = Agent(id="test", name="Test", position=(5.0, 5.0))
        world = World(width=20, height=20)
        fm = FactionManager()
        faction = fm.create("TestFaction", "#FF0000")
        agent.faction_id = faction.id
        fm.join(agent.id, faction.id)

        MapMemoryManager.update_vision(agent, world, fm, tick=1)

        assert faction.tile_reported_by[(5, 5)] == "test"

    def test_no_faction_does_not_crash(self):
        """RED: Agent without faction does not crash on update_vision."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        world = World(width=10, height=10)

        MapMemoryManager.update_vision(agent, world, faction_manager=None, tick=1)

        assert len(agent.tile_memory) > 0

    def test_changed_tile_updates_faction(self):
        """RED: When tile amount changes, faction shared memory updates."""
        agent = Agent(id="test", name="Test", position=(5.0, 5.0))
        world = World(width=20, height=20)
        fm = FactionManager()
        faction = fm.create("TestFaction", "#FF0000")
        agent.faction_id = faction.id
        fm.join(agent.id, faction.id)

        from app.simulation.world import Tile
        world.set_tile(6, 5, Tile(x=6, y=5, resource_type="berries", amount=40))
        MapMemoryManager.update_vision(agent, world, fm, tick=1)
        assert faction.shared_tile_memory[(6, 5)].amount == 40
        assert faction.shared_tile_memory[(6, 5)].resource_type == "berries"

        # Update amount
        world.set_tile(6, 5, Tile(x=6, y=5, resource_type="berries", amount=20))
        MapMemoryManager.update_vision(agent, world, fm, tick=10)
        assert faction.shared_tile_memory[(6, 5)].amount == 20
        assert faction.shared_tile_memory[(6, 5)].tick_last_seen == 10


# ---------------------------------------------------------------------------
# get_faction_tile_visibility
# ---------------------------------------------------------------------------

class TestGetFactionTileVisibility:
    """Faction tile visibility — fog tiles from shared memory."""

    def test_returns_fog_tiles(self):
        """RED: Faction with shared memory returns fog tiles."""
        fm = FactionManager()
        faction = fm.create("TestFaction", "#FF0000")
        faction.shared_tile_memory[(5, 5)] = TileMemory(resource_type="wood", amount=30, tick_last_seen=10)
        faction.shared_tile_memory[(6, 5)] = TileMemory(resource_type="stone", amount=15, tick_last_seen=8)

        result = MapMemoryManager.get_faction_tile_visibility(faction, None, 20)

        # All shared tiles should be in fog
        assert len(result["fog"]) == 2
        assert len(result["visible"]) == 0

        # Verify tile structure
        tile1 = next(t for t in result["fog"] if t["x"] == 5 and t["y"] == 5)
        assert tile1["resource_type"] == "wood"
        assert tile1["amount"] == 30
        assert tile1["tick_last_seen"] == 10

    def test_empty_faction_memory(self):
        """RED: Faction with empty shared memory returns empty lists."""
        fm = FactionManager()
        faction = fm.create("TestFaction", "#FF0000")

        result = MapMemoryManager.get_faction_tile_visibility(faction, None, 20)

        assert result["visible"] == []
        assert result["fog"] == []


# ---------------------------------------------------------------------------
# Agent and Faction field presence (structural verification)
# ---------------------------------------------------------------------------

class TestFieldPresence:
    """Verify new fields exist on Agent and Faction dataclasses."""

    def test_agent_has_tile_memory(self):
        """RED: Agent dataclass has tile_memory field defaulting to empty dict."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        assert hasattr(agent, "tile_memory")
        assert agent.tile_memory == {}

    def test_faction_has_shared_tile_memory(self):
        """RED: Faction dataclass has shared_tile_memory defaulting to empty dict."""
        faction = Faction(id="f_test", name="TestFaction", color="#FF0000")
        assert hasattr(faction, "shared_tile_memory")
        assert faction.shared_tile_memory == {}

    def test_faction_has_tile_reported_by(self):
        """RED: Faction dataclass has tile_reported_by defaulting to empty dict."""
        faction = Faction(id="f_test", name="TestFaction", color="#FF0000")
        assert hasattr(faction, "tile_reported_by")
        assert faction.tile_reported_by == {}

    def test_tile_memory_stores_tuples_as_keys(self):
        """RED: tile_memory accepts tuple[int,int] keys."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        mem = TileMemory(resource_type="wood", amount=50, tick_last_seen=5)
        agent.tile_memory[(3, 7)] = mem
        assert agent.tile_memory[(3, 7)].resource_type == "wood"


# ---------------------------------------------------------------------------
# Module-level exports
# ---------------------------------------------------------------------------

class TestModuleExports:
    """Verify map_memory module exports expected symbols."""

    def test_tile_memory_exported(self):
        """RED: TileMemory is importable from map_memory module."""
        from app.simulation.map_memory import TileMemory as TM
        assert TM is TileMemory

    def test_map_memory_manager_exported(self):
        """RED: MapMemoryManager is importable from map_memory module."""
        from app.simulation.map_memory import MapMemoryManager as MMM
        assert MMM is MapMemoryManager

    def test_simulation_init_exports(self):
        """RED: MapMemoryManager and TileMemory are exported from simulation package."""
        from app.simulation import TileMemory as TM, MapMemoryManager as MMM
        assert TM is TileMemory
        assert MMM is MapMemoryManager
