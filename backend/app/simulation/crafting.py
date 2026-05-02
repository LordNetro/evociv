"""Crafting system: recipes, requirements, and atomic crafting."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.core.definitions import DEFINITIONS
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


# Module-level alias for backward compatibility — data now lives in DEFINITIONS.recipes
RECIPES: dict[str, Recipe] = DEFINITIONS.recipes  # type: ignore[assignment]


class CraftingManager:
    """Manages recipe validation and atomic crafting."""

    @staticmethod
    def can_craft(agent: Agent, recipe_name: str, world: World | None = None) -> bool:
        """Check if *agent* can craft *recipe_name* given current inventory and optional world."""
        recipe = DEFINITIONS.recipes.get(recipe_name)
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
        recipe = DEFINITIONS.recipes.get(recipe_name)
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
