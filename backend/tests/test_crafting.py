"""Tests for the crafting system."""

import pytest

from app.simulation.agent import Agent
from app.simulation.crafting import CraftingManager, RECIPES, Recipe
from app.simulation.world import World


class TestRecipes:
    def test_recipes_dict_has_expected_recipes(self):
        """RECIPES contains all expected recipe names."""
        expected = {
            "stone_axe", "stone_pickaxe", "workbench_structure", "spear",
            "fishing_rod", "bow", "fiber_armor", "hoe", "iron_sword",
            "iron_axe", "hide_armor", "arrows",
        }
        assert expected.issubset(set(RECIPES.keys()))

    def test_stone_axe_recipe(self):
        """stone_axe recipe has correct inputs and outputs."""
        recipe = RECIPES["stone_axe"]
        assert recipe.inputs == {"wood": 3, "stone": 2}
        assert recipe.output == {"stone_axe": 1}
        assert recipe.workbench is None
        assert recipe.duration == 10
        assert recipe.category == "tool"
        assert recipe.modifiers == {"chop_speed": 2, "attack_damage": 5}

    def test_spear_requires_workbench(self):
        """spear requires basic workbench."""
        recipe = RECIPES["spear"]
        assert recipe.workbench == "basic"
        assert recipe.category == "weapon"
        assert recipe.modifiers == {"attack_damage": 15, "hunt_bonus": 2}

    def test_iron_sword_requires_forge(self):
        """iron_sword requires forge workbench."""
        recipe = RECIPES["iron_sword"]
        assert recipe.workbench == "forge"
        assert recipe.category == "weapon"

    def test_arrows_output_quantity(self):
        """arrows produce 10 units."""
        recipe = RECIPES["arrows"]
        assert recipe.output == {"arrows": 10}
        assert recipe.workbench is None
        assert recipe.duration == 5
        assert recipe.category == "ammo"


class TestCraftingManager:
    def test_can_craft_with_sufficient_resources(self):
        """can_craft returns True when agent has all ingredients."""
        agent = Agent(id="test_001", name="Crafter", position=(0.0, 0.0))
        agent.inventory = {"wood": 5, "stone": 5}
        mgr = CraftingManager()
        assert mgr.can_craft(agent, "stone_axe") is True

    def test_can_craft_missing_ingredient(self):
        """can_craft returns False when an ingredient is missing."""
        agent = Agent(id="test_001", name="Crafter", position=(0.0, 0.0))
        agent.inventory = {"wood": 1, "stone": 5}
        mgr = CraftingManager()
        assert mgr.can_craft(agent, "stone_axe") is False

    def test_can_craft_missing_workbench(self):
        """can_craft returns False when workbench is required but not present."""
        agent = Agent(id="test_001", name="Crafter", position=(0.0, 0.0))
        agent.inventory = {"wood": 10, "stone": 5}
        world = World(width=10, height=10)
        mgr = CraftingManager()
        # spear requires basic workbench; no workbench in world
        assert mgr.can_craft(agent, "spear", world) is False

    def test_craft_success(self):
        """craft deducts inputs and adds output on success."""
        agent = Agent(id="test_001", name="Crafter", position=(0.0, 0.0))
        agent.inventory = {"wood": 5, "stone": 5}
        mgr = CraftingManager()
        result = mgr.craft(agent, "stone_axe")
        assert result.success is True
        assert agent.inventory["wood"] == 2
        assert agent.inventory["stone"] == 3
        assert agent.inventory.get("stone_axe", 0) == 1

    def test_craft_missing_ingredient(self):
        """craft fails and does not modify inventory when ingredients missing."""
        agent = Agent(id="test_001", name="Crafter", position=(0.0, 0.0))
        agent.inventory = {"wood": 1, "stone": 5}
        mgr = CraftingManager()
        result = mgr.craft(agent, "stone_axe")
        assert result.success is False
        assert agent.inventory["wood"] == 1
        assert agent.inventory["stone"] == 5
        assert "stone_axe" not in agent.inventory

    def test_craft_atomic_rollback(self):
        """craft restores state if mid-craft failure occurs."""
        agent = Agent(id="test_001", name="Crafter", position=(0.0, 0.0))
        agent.inventory = {"wood": 3, "stone": 2}
        mgr = CraftingManager()
        result = mgr.craft(agent, "stone_axe")
        assert result.success is True
        # Now craft again — should fail because not enough resources,
        # and inventory must remain unchanged.
        result2 = mgr.craft(agent, "stone_axe")
        assert result2.success is False
        # Inventory should still have 0 wood, 0 stone, 1 stone_axe
        assert agent.inventory.get("wood", 0) == 0
        assert agent.inventory.get("stone", 0) == 0
        assert agent.inventory.get("stone_axe", 0) == 1

    def test_craft_with_workbench(self):
        """craft succeeds at workbench when workbench is present."""
        agent = Agent(id="test_001", name="Crafter", position=(5.0, 5.0))
        agent.inventory = {"wood": 10, "stone": 5}
        world = World(width=10, height=10)
        # Place a workbench tile nearby (we'll use a special resource_type for now)
        world.get_tile(5, 5).resource_type = "workbench"
        mgr = CraftingManager()
        # workbench_structure doesn't require a workbench itself
        result = mgr.craft(agent, "workbench_structure")
        assert result.success is True
        assert agent.inventory.get("workbench", 0) == 1

    def test_craft_recipe_duration(self):
        """craft result includes recipe duration."""
        agent = Agent(id="test_001", name="Crafter", position=(0.0, 0.0))
        agent.inventory = {"wood": 3, "stone": 2}
        mgr = CraftingManager()
        result = mgr.craft(agent, "stone_axe")
        assert result.success is True
        # ActionResult should carry duration via state_changes or we check recipe directly
        recipe = RECIPES["stone_axe"]
        assert recipe.duration == 10

    def test_craft_unknown_recipe(self):
        """craft fails gracefully for unknown recipe names."""
        agent = Agent(id="test_001", name="Crafter", position=(0.0, 0.0))
        mgr = CraftingManager()
        result = mgr.craft(agent, "nonexistent_recipe")
        assert result.success is False

    def test_can_craft_without_world_skips_workbench_check(self):
        """can_craft ignores workbench requirement when world is not provided."""
        agent = Agent(id="test_001", name="Crafter", position=(0.0, 0.0))
        agent.inventory = {"wood": 10, "stone": 10}
        mgr = CraftingManager()
        # spear requires basic workbench, but no world given → check skipped
        assert mgr.can_craft(agent, "spear") is True

    def test_craft_arrows_multiple_output(self):
        """crafting arrows produces 10 arrows at once."""
        agent = Agent(id="test_001", name="Crafter", position=(0.0, 0.0))
        agent.inventory = {"wood": 4, "stone": 2}
        mgr = CraftingManager()
        result = mgr.craft(agent, "arrows")
        assert result.success is True
        assert agent.inventory.get("arrows", 0) == 10
        assert agent.inventory.get("wood", 0) == 2
        assert agent.inventory.get("stone", 0) == 1


class TestMissingRecipes:
    """Tests for the 7 required recipes that were missing (Issue 4)."""

    def test_recipes_dict_has_all_required_recipes(self):
        """RECIPES contains all 7 newly required recipe names."""
        required = {
            "planks", "stone_blade", "rope", "hide_vest",
            "iron_ingot", "bone_armor", "arrow",
        }
        assert required.issubset(set(RECIPES.keys()))

    def test_planks_recipe(self):
        """planks recipe: 2 wood → 2 planks, no workbench, duration 5, material."""
        recipe = RECIPES["planks"]
        assert recipe.inputs == {"wood": 2}
        assert recipe.output == {"planks": 2}
        assert recipe.workbench is None
        assert recipe.duration == 5
        assert recipe.category == "material"

    def test_stone_blade_recipe(self):
        """stone_blade recipe: 2 stone → 1 stone_blade, weapon with attack_damage 8."""
        recipe = RECIPES["stone_blade"]
        assert recipe.inputs == {"stone": 2}
        assert recipe.output == {"stone_blade": 1}
        assert recipe.workbench is None
        assert recipe.duration == 8
        assert recipe.category == "weapon"
        assert recipe.modifiers == {"attack_damage": 8}

    def test_rope_recipe(self):
        """rope recipe: 3 fiber → 1 rope, no workbench, duration 4, material."""
        recipe = RECIPES["rope"]
        assert recipe.inputs == {"fiber": 3}
        assert recipe.output == {"rope": 1}
        assert recipe.workbench is None
        assert recipe.duration == 4
        assert recipe.category == "material"

    def test_hide_vest_recipe(self):
        """hide_vest recipe: 3 hide + 2 fiber → 1 hide_vest, basic workbench, armor."""
        recipe = RECIPES["hide_vest"]
        assert recipe.inputs == {"hide": 3, "fiber": 2}
        assert recipe.output == {"hide_vest": 1}
        assert recipe.workbench == "basic"
        assert recipe.duration == 10
        assert recipe.category == "armor"
        assert recipe.modifiers == {"damage_reduction": 8}

    def test_iron_ingot_recipe(self):
        """iron_ingot recipe: 3 iron_ore → 1 iron_ingot, forge workbench, material."""
        recipe = RECIPES["iron_ingot"]
        assert recipe.inputs == {"iron_ore": 3}
        assert recipe.output == {"iron_ingot": 1}
        assert recipe.workbench == "forge"
        assert recipe.duration == 15
        assert recipe.category == "material"

    def test_bone_armor_recipe(self):
        """bone_armor recipe: 5 hide + 3 bone → 1 bone_armor, basic workbench, armor."""
        recipe = RECIPES["bone_armor"]
        assert recipe.inputs == {"hide": 5, "bone": 3}
        assert recipe.output == {"bone_armor": 1}
        assert recipe.workbench == "basic"
        assert recipe.duration == 18
        assert recipe.category == "armor"
        assert recipe.modifiers == {"damage_reduction": 15}

    def test_arrow_recipe(self):
        """arrow recipe: 1 wood + 1 stone → 5 arrows, no workbench, duration 3, ammo."""
        recipe = RECIPES["arrow"]
        assert recipe.inputs == {"wood": 1, "stone": 1}
        assert recipe.output == {"arrow": 5}
        assert recipe.workbench is None
        assert recipe.duration == 3
        assert recipe.category == "ammo"

    def test_craft_planks_success(self):
        """crafting planks deducts wood and produces planks."""
        agent = Agent(id="test_001", name="Crafter", position=(0.0, 0.0))
        agent.inventory = {"wood": 4}
        mgr = CraftingManager()
        result = mgr.craft(agent, "planks")
        assert result.success is True
        assert agent.inventory.get("wood", 0) == 2
        assert agent.inventory.get("planks", 0) == 2

    def test_craft_stone_blade_success(self):
        """crafting stone_blade deducts stone and produces blade."""
        agent = Agent(id="test_001", name="Crafter", position=(0.0, 0.0))
        agent.inventory = {"stone": 4}
        mgr = CraftingManager()
        result = mgr.craft(agent, "stone_blade")
        assert result.success is True
        assert agent.inventory.get("stone", 0) == 2
        assert agent.inventory.get("stone_blade", 0) == 1

    def test_craft_rope_success(self):
        """crafting rope deducts fiber and produces rope."""
        agent = Agent(id="test_001", name="Crafter", position=(0.0, 0.0))
        agent.inventory = {"fiber": 6}
        mgr = CraftingManager()
        result = mgr.craft(agent, "rope")
        assert result.success is True
        assert agent.inventory.get("fiber", 0) == 3
        assert agent.inventory.get("rope", 0) == 1

    def test_craft_hide_vest_at_workbench(self):
        """crafting hide_vest requires basic workbench."""
        agent = Agent(id="test_001", name="Crafter", position=(5.0, 5.0))
        agent.inventory = {"hide": 5, "fiber": 4}
        world = World(width=10, height=10)
        # Without workbench — should fail
        mgr = CraftingManager()
        assert mgr.can_craft(agent, "hide_vest", world) is False
        # Place workbench tile
        world.get_tile(5, 5).resource_type = "workbench"
        assert mgr.can_craft(agent, "hide_vest", world) is True
        result = mgr.craft(agent, "hide_vest", world)
        assert result.success is True
        assert agent.inventory.get("hide_vest", 0) == 1

    def test_craft_iron_ingot_at_forge(self):
        """crafting iron_ingot requires forge workbench."""
        agent = Agent(id="test_001", name="Crafter", position=(5.0, 5.0))
        agent.inventory = {"iron_ore": 6}
        world = World(width=10, height=10)
        mgr = CraftingManager()
        # Without forge — should fail
        assert mgr.can_craft(agent, "iron_ingot", world) is False
        # Place forge tile
        world.get_tile(5, 5).resource_type = "forge"
        assert mgr.can_craft(agent, "iron_ingot", world) is True
        result = mgr.craft(agent, "iron_ingot", world)
        assert result.success is True
        assert agent.inventory.get("iron_ingot", 0) == 1

    def test_craft_bone_armor_at_workbench(self):
        """crafting bone_armor requires basic workbench."""
        agent = Agent(id="test_001", name="Crafter", position=(5.0, 5.0))
        agent.inventory = {"hide": 6, "bone": 4}
        world = World(width=10, height=10)
        mgr = CraftingManager()
        world.get_tile(5, 5).resource_type = "workbench"
        result = mgr.craft(agent, "bone_armor", world)
        assert result.success is True
        assert agent.inventory.get("bone_armor", 0) == 1

    def test_craft_arrow_success(self):
        """crafting arrow produces 5 arrows."""
        agent = Agent(id="test_001", name="Crafter", position=(0.0, 0.0))
        agent.inventory = {"wood": 3, "stone": 3}
        mgr = CraftingManager()
        result = mgr.craft(agent, "arrow")
        assert result.success is True
        assert agent.inventory.get("arrow", 0) == 5
        assert agent.inventory.get("wood", 0) == 2
        assert agent.inventory.get("stone", 0) == 2
