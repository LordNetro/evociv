"""Crafting system: recipes, requirements, and atomic crafting."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.simulation.actions import ActionResult
from app.simulation.agent import Agent
from app.simulation.world import World


@dataclass
class Recipe:
    name: str
    inputs: dict[str, int]
    output: dict[str, int]
    workbench: str | None = None
    workbench_level: int = 0
    duration: int = 10
    category: str = "misc"
    modifiers: dict[str, Any] = None

    def __post_init__(self):
        if self.modifiers is None:
            self.modifiers = {}


RECIPES: dict[str, Recipe] = {
    "stone_axe": Recipe(
        name="stone_axe",
        inputs={"wood": 3, "stone": 2},
        output={"stone_axe": 1},
        duration=10,
        category="tool",
        modifiers={"chop_speed": 2, "attack_damage": 5},
    ),
    "stone_pickaxe": Recipe(
        name="stone_pickaxe",
        inputs={"wood": 3, "stone": 3},
        output={"stone_pickaxe": 1},
        duration=10,
        category="tool",
        modifiers={"mine_speed": 2},
    ),
    "workbench_structure": Recipe(
        name="workbench_structure",
        inputs={"wood": 10, "stone": 5},
        output={"workbench": 1},
        duration=20,
        category="structure",
    ),
    "spear": Recipe(
        name="spear",
        inputs={"wood": 4, "stone": 3},
        output={"spear": 1},
        workbench="basic",
        duration=15,
        category="weapon",
        modifiers={"attack_damage": 15, "hunt_bonus": 2},
    ),
    "fishing_rod": Recipe(
        name="fishing_rod",
        inputs={"wood": 5, "fiber": 3},
        output={"fishing_rod": 1},
        workbench="basic",
        duration=12,
        category="tool",
        modifiers={"fish_bonus": 2},
    ),
    "bow": Recipe(
        name="bow",
        inputs={"wood": 6, "fiber": 4},
        output={"bow": 1},
        workbench="basic",
        duration=18,
        category="weapon",
        modifiers={"attack_damage": 12, "ranged": True},
    ),
    "fiber_armor": Recipe(
        name="fiber_armor",
        inputs={"fiber": 8},
        output={"fiber_armor": 1},
        duration=8,
        category="armor",
        modifiers={"damage_reduction": 0.3},
    ),
    "hoe": Recipe(
        name="hoe",
        inputs={"wood": 4, "stone": 2},
        output={"hoe": 1},
        duration=8,
        category="tool",
        modifiers={"farm_speed": 2},
    ),
    "iron_sword": Recipe(
        name="iron_sword",
        inputs={"iron_ore": 5, "wood": 2},
        output={"iron_sword": 1},
        workbench="forge",
        duration=25,
        category="weapon",
        modifiers={"attack_damage": 25},
    ),
    "iron_axe": Recipe(
        name="iron_axe",
        inputs={"iron_ore": 4, "wood": 2},
        output={"iron_axe": 1},
        workbench="forge",
        duration=22,
        category="tool",
        modifiers={"chop_speed": 4},
    ),
    "hide_armor": Recipe(
        name="hide_armor",
        inputs={"hide": 5, "fiber": 3},
        output={"hide_armor": 1},
        workbench="basic",
        duration=15,
        category="armor",
        modifiers={"damage_reduction": 0.5},
    ),
    "arrows": Recipe(
        name="arrows",
        inputs={"wood": 2, "stone": 1},
        output={"arrows": 10},
        duration=5,
        category="ammo",
    ),
    "planks": Recipe(
        name="planks",
        inputs={"wood": 2},
        output={"planks": 2},
        duration=5,
        category="material",
    ),
    "stone_blade": Recipe(
        name="stone_blade",
        inputs={"stone": 2},
        output={"stone_blade": 1},
        duration=8,
        category="weapon",
        modifiers={"attack_damage": 8},
    ),
    "rope": Recipe(
        name="rope",
        inputs={"fiber": 3},
        output={"rope": 1},
        duration=4,
        category="material",
    ),
    "hide_vest": Recipe(
        name="hide_vest",
        inputs={"hide": 3, "fiber": 2},
        output={"hide_vest": 1},
        workbench="basic",
        duration=10,
        category="armor",
        modifiers={"damage_reduction": 8},
    ),
    "iron_ingot": Recipe(
        name="iron_ingot",
        inputs={"iron_ore": 3},
        output={"iron_ingot": 1},
        workbench="forge",
        duration=15,
        category="material",
    ),
    "bone_armor": Recipe(
        name="bone_armor",
        inputs={"hide": 5, "bone": 3},
        output={"bone_armor": 1},
        workbench="basic",
        duration=18,
        category="armor",
        modifiers={"damage_reduction": 15},
    ),
    "arrow": Recipe(
        name="arrow",
        inputs={"wood": 1, "stone": 1},
        output={"arrow": 5},
        duration=3,
        category="ammo",
    ),
}


class CraftingManager:
    """Manages recipe validation and atomic crafting."""

    @staticmethod
    def can_craft(agent: Agent, recipe_name: str, world: World | None = None) -> bool:
        """Check if *agent* can craft *recipe_name* given current inventory and optional world."""
        recipe = RECIPES.get(recipe_name)
        if not recipe:
            return False

        # Check inputs
        for item, qty in recipe.inputs.items():
            if agent.inventory.get(item, 0) < qty:
                return False

        # Check workbench proximity if required and world provided
        if recipe.workbench and world is not None:
            if not CraftingManager._has_workbench_nearby(agent, recipe.workbench, world):
                return False

        return True

    @staticmethod
    def craft(agent: Agent, recipe_name: str, world: World | None = None) -> ActionResult:
        """Atomically craft *recipe_name*. Deducts inputs and adds outputs on success."""
        recipe = RECIPES.get(recipe_name)
        if not recipe:
            return ActionResult(
                success=False,
                events=[{"type": "craft_failed", "reason": "unknown recipe"}],
            )

        if not CraftingManager.can_craft(agent, recipe_name, world):
            return ActionResult(
                success=False,
                events=[{"type": "craft_failed", "reason": "requirements not met"}],
            )

        # Atomic operation: snapshot inventory, modify, rollback on exception
        original_inventory = deepcopy(agent.inventory)
        try:
            for item, qty in recipe.inputs.items():
                agent.inventory[item] -= qty
                if agent.inventory[item] == 0:
                    del agent.inventory[item]

            for item, qty in recipe.output.items():
                agent.inventory[item] = agent.inventory.get(item, 0) + qty
        except Exception:
            agent.inventory = original_inventory
            return ActionResult(
                success=False,
                events=[{"type": "craft_failed", "reason": "exception during craft"}],
            )

        return ActionResult(
            success=True,
            action_summary=f"crafted {recipe_name}",
            events=[{"type": "craft", "recipe": recipe_name, "output": recipe.output}],
            state_changes={"inventory": dict(agent.inventory)},
        )

    @staticmethod
    def _has_workbench_nearby(agent: Agent, workbench_type: str, world: World) -> bool:
        """Check if a workbench of the given type is in the 3x3 area around the agent."""
        cx, cy = int(agent.position[0]), int(agent.position[1])
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < world.width and 0 <= ny < world.height:
                    tile = world.get_tile(nx, ny)
                    # Support both tile resource type and future structure types
                    if tile.resource_type == workbench_type or tile.resource_type == "workbench":
                        return True
        return False
