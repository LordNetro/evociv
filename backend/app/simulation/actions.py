"""Action system: types, results, handlers, and registry."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from app.core.definitions import DEFINITIONS
from app.simulation.agent import Agent
from app.simulation.skills import SkillManager
from app.simulation.status_effects import StatusEffectManager
from app.simulation.emotions import EmotionManager
from app.simulation.world import World


# ---------------------------------------------------------------------------
# Tool modifiers (maps item name → its passive modifiers)
# Derived from DEFINITIONS.recipes at import time.
# ---------------------------------------------------------------------------

ITEM_MODIFIERS: dict[str, dict[str, Any]] = {}
for _recipe in DEFINITIONS.recipes.values():
    if _recipe.modifiers:
        for _output_name in _recipe.output:
            ITEM_MODIFIERS[_output_name] = dict(_recipe.modifiers)


class ActionType(str, Enum):
    MOVE = "move"
    CHOP = "chop"
    DRINK = "drink"
    EAT = "eat"
    GATHER = "gather"
    REST = "rest"
    REPRODUCE = "reproduce"
    TRADE = "trade"
    SOCIALIZE = "socialize"
    FEED_CHILD = "feed_child"
    MINE = "mine"
    EXPLORE = "explore"
    CRAFT = "craft"
    HUNT = "hunt"
    FISH = "fish"
    ATTACK = "attack"
    GUARD = "guard"
    HEAL = "heal"
    BUILD = "build"
    FARM = "farm"


@dataclass
class ActionResult:
    success: bool = True
    events: list[dict] = field(default_factory=list)
    interrupted: bool = False
    state_changes: dict[str, Any] = field(default_factory=dict)
    action_type: ActionType | None = None
    action_summary: str = ""


ActionHandler = Callable[..., ActionResult]


# Duration multipliers when a specific tool is used for an action
# Derived from DEFINITIONS.actions at import time.
TOOL_DURATION_MULTIPLIERS: dict[tuple[str, ActionType], float] = {}
for _action_name, _action_def in DEFINITIONS.actions.items():
    _action_type = ActionType(_action_name)
    for _mult_entry in _action_def.tool_multipliers:
        TOOL_DURATION_MULTIPLIERS[(_mult_entry["item"], _action_type)] = _mult_entry["multiplier"]


def get_item_modifiers(agent: Agent) -> dict[str, Any]:
    """Return combined modifiers from all items in the agent's inventory."""
    combined: dict[str, Any] = {}
    for item, qty in agent.inventory.items():
        if qty > 0 and item in ITEM_MODIFIERS:
            for key, value in ITEM_MODIFIERS[item].items():
                # For numeric modifiers, keep the highest value (best gear wins)
                if key in combined and isinstance(value, (int, float)) and isinstance(combined[key], (int, float)):
                    if isinstance(value, int) and isinstance(combined[key], int):
                        combined[key] = max(combined[key], value)
                    else:
                        combined[key] = max(float(combined[key]), float(value))
                else:
                    combined[key] = value
    return combined


def apply_tool_modifier(agent: Agent, action_type: ActionType, base_duration: int) -> int:
    """Apply tool speed modifiers to *base_duration* for *action_type*."""
    multiplier = 1.0
    for item, qty in agent.inventory.items():
        if qty <= 0:
            continue
        key = (item, action_type)
        if key in TOOL_DURATION_MULTIPLIERS:
            multiplier = min(multiplier, TOOL_DURATION_MULTIPLIERS[key])
    return max(1, int(base_duration * multiplier))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _agent_grid_pos(agent: Agent) -> tuple[int, int]:
    return (int(agent.position[0]), int(agent.position[1]))


def _tiles_on_or_adjacent(agent: Agent, world: World) -> list[tuple[int, int, Any]]:
    """Return (x, y, tile) for the 3x3 area centred on the agent's grid cell."""
    cx, cy = _agent_grid_pos(agent)
    results: list[tuple[int, int, Any]] = []
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < world.width and 0 <= ny < world.height:
                results.append((nx, ny, world.get_tile(nx, ny)))
    return results


def _inventory_capacity(agent: Agent, resource_key: str) -> bool:
    """Return True if agent can receive one more unit of *resource_key*."""
    max_amount = 40 if getattr(agent, "_storage_nearby", False) else 20
    return agent.inventory.get(resource_key, 0) < max_amount


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_move(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Advance the agent along *agent.move_path* or compute a new one from *target*."""
    # Need a path to follow
    if not agent.move_path:
        if target is None:
            return ActionResult(
                success=False,
                events=[{"type": "move_failed", "reason": "no target"}],
                interrupted=True,
            )
        start = _agent_grid_pos(agent)
        if start == target:
            return ActionResult(
                success=True,
                state_changes={"position": agent.position},
            )
        path = world.find_path(start, target)
        if not path:
            return ActionResult(
                success=False,
                events=[{"type": "move_failed", "reason": "no path found"}],
                interrupted=True,
            )
        agent.move_path = path
        agent.target_position = (float(target[0]), float(target[1]))
        agent.move_progress = 0.0

    # Advance one step per tick along the stored path
    agent.move_progress += 1.0
    idx = int(agent.move_progress) - 1

    if 0 <= idx < len(agent.move_path):
        waypoint = agent.move_path[idx]
        agent.position = (float(waypoint[0]), float(waypoint[1]))

    # Arrived at destination?
    if agent.move_progress >= len(agent.move_path):
        agent.move_path = []
        agent.target_position = None
        return ActionResult(
            success=True,
            action_type=ActionType.MOVE,
            action_summary=f"position:{agent.position}",
            state_changes={"position": agent.position},
        )

    return ActionResult(
        success=True,
        action_type=ActionType.MOVE,
        action_summary=f"position:{agent.position}",
        state_changes={"position": agent.position},
    )


def handle_chop(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Chop a nearby tree, adding wood to inventory."""
    for x, y, tile in _tiles_on_or_adjacent(agent, world):
        if tile.resource_type == "tree" and tile.amount > 0:
            if not _inventory_capacity(agent, "wood"):
                return ActionResult(
                    success=False,
                    action_type=ActionType.CHOP,
                    action_summary="chop_failed: inventory full",
                    events=[{"type": "chop_failed", "reason": "inventory full"}],
                )
            tile.amount = max(0, tile.amount - 1)
            agent.inventory["wood"] = agent.inventory.get("wood", 0) + 1

            if tile.amount == 0:
                tile.resource_type = None

            world.set_tile(x, y, tile)
            return ActionResult(
                success=True,
                action_type=ActionType.CHOP,
                action_summary="wood:+1",
                events=[{"type": "chop", "resource": "tree", "amount": 1}],
                state_changes={"inventory": dict(agent.inventory)},
            )

    return ActionResult(
        success=False,
        action_type=ActionType.CHOP,
        action_summary="chop_failed: no tree nearby",
        events=[{"type": "chop_failed", "reason": "no tree nearby"}],
    )


def handle_drink(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Drink from a nearby water source, reducing thirst to 0 (fully hydrated)."""
    if agent.is_child:
        return ActionResult(
            success=False,
            action_type=ActionType.DRINK,
            action_summary="drink_failed: children cannot drink independently",
            events=[{"type": "drink_failed", "reason": "child cannot drink independently"}],
        )
    for x, y, tile in _tiles_on_or_adjacent(agent, world):
        if tile.resource_type == "water":
            agent.thirst = 0.0
            return ActionResult(
                success=True,
                action_type=ActionType.DRINK,
                action_summary="thirst:0",
                events=[{"type": "drink", "resource": "water"}],
                state_changes={"thirst": agent.thirst},
            )

    return ActionResult(
        success=False,
        action_type=ActionType.DRINK,
        action_summary="drink_failed: no water nearby",
        events=[{"type": "drink_failed", "reason": "no water nearby"}],
    )


def handle_eat(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Consume one unit of berries from inventory to reduce hunger."""
    if agent.is_child:
        return ActionResult(
            success=False,
            action_type=ActionType.EAT,
            action_summary="eat_failed: children cannot eat independently",
            events=[{"type": "eat_failed", "reason": "child cannot eat independently"}],
        )
    if agent.inventory.get("berries", 0) > 0:
        agent.inventory["berries"] -= 1
        agent.hunger = max(0.0, agent.hunger - 20)

        # F2: reveal hidden properties from nearby tile with matching subtype
        knowledge_learned = ""
        for x, y, tile in _tiles_on_or_adjacent(agent, world):
            if tile.resource_type == "berries" and tile.subtype:
                agent.knowledge[tile.subtype] = dict(tile.hidden_properties)
                knowledge_learned = f", learned: {tile.subtype} is {tile.hidden_properties}"
                break

        # Apply poisoned status effect if berries are poisonous
        for x, y, tile in _tiles_on_or_adjacent(agent, world):
            if tile.resource_type == "berries" and tile.subtype:
                if tile.hidden_properties.get("is_poisonous"):
                    StatusEffectManager.apply(agent, "poisoned", source="food")
                break

        return ActionResult(
            success=True,
            action_type=ActionType.EAT,
            action_summary=f"hunger:-20, berries:-1{knowledge_learned}",
            events=[{"type": "eat", "food": "berries"}],
            state_changes={"hunger": agent.hunger, "inventory": dict(agent.inventory)},
        )

    return ActionResult(
        success=False,
        action_type=ActionType.EAT,
        action_summary="eat_failed: no food",
        events=[{"type": "eat_failed", "reason": "no food"}],
    )


def handle_gather(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Gather one unit from a nearby resource (berries, tree, stone, iron_ore).

    Stone and iron_ore can be gathered slowly by anyone — mining with a pickaxe is faster.
    """
    for x, y, tile in _tiles_on_or_adjacent(agent, world):
        rt = tile.resource_type
        if rt in ("berries", "tree", "stone", "iron_ore") and tile.amount > 0:
            # Map resource type to inventory key
            key_map = {
                "berries": "berries",
                "tree": "wood",
                "stone": "stone",
                "iron_ore": "iron_ore",
            }
            key = key_map[rt]
            if not _inventory_capacity(agent, key):
                return ActionResult(
                    success=False,
                    action_type=ActionType.GATHER,
                    action_summary="gather_failed: inventory full",
                    events=[{"type": "gather_failed", "reason": "inventory full"}],
                )
            tile.amount = max(0, tile.amount - 1)
            agent.inventory[key] = agent.inventory.get(key, 0) + 1

            if tile.amount == 0:
                tile.resource_type = None

            world.set_tile(x, y, tile)
            return ActionResult(
                success=True,
                action_type=ActionType.GATHER,
                action_summary=f"{key}:+1",
                events=[{"type": "gather", "resource": key, "amount": 1}],
                state_changes={"inventory": dict(agent.inventory)},
            )

    return ActionResult(
        success=False,
        action_type=ActionType.GATHER,
        action_summary="gather_failed: no gatherable resource nearby",
        events=[{"type": "gather_failed", "reason": "no gatherable resource nearby"}],
    )


def handle_rest(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Rest in place, recovering energy. House structures double recovery."""
    cx, cy = _agent_grid_pos(agent)
    structure = world.structures.get_structure_at((cx, cy))
    if structure is not None and structure.structure_type == "house":
        energy_gained = 20
    else:
        energy_gained = 10
    agent.energy = min(100.0, agent.energy + energy_gained)
    return ActionResult(
        success=True,
        action_type=ActionType.REST,
        action_summary=f"energy:+{energy_gained}",
        events=[{"type": "rest", "energy_gained": energy_gained}],
        state_changes={"energy": agent.energy},
    )


def handle_reproduce(
    agent: Agent,
    world: World | None = None,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Stub — actual reproduction logic is in SimulationEngine."""
    return ActionResult(
        success=True,
        action_type=ActionType.REPRODUCE,
        action_summary="reproduced",
        events=[{"type": "reproduce"}],
    )


# ---------------------------------------------------------------------------
# Registry & metadata
# ---------------------------------------------------------------------------

def handle_trade(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Validate trade offer and enqueue proposal in target's conversation queue."""
    if step is None:
        return ActionResult(
            success=False,
            action_type=ActionType.TRADE,
            action_summary="trade_failed: no trade step provided",
            events=[{"type": "trade_failed", "reason": "no trade step"}],
        )

    offer = step.get("offer", {})
    request = step.get("request", {})

    # Validate proposer has offer resources
    for res, qty in offer.items():
        if agent.inventory.get(res, 0) < qty:
            return ActionResult(
                success=False,
                action_type=ActionType.TRADE,
                action_summary=f"trade_failed: insufficient {res}",
                events=[{"type": "trade_failed", "reason": f"insufficient {res}"}],
            )

    return ActionResult(
        success=True,
        action_type=ActionType.TRADE,
        action_summary=f"trade proposed: offer={offer}, request={request}",
        events=[{"type": "trade", "offer": offer, "request": request}],
    )


def handle_socialize(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Stub — socialization is processed via conversation queue."""
    return ActionResult(
        success=True,
        action_type=ActionType.SOCIALIZE,
        action_summary="socialized",
        events=[{"type": "socialize"}],
    )


def handle_feed_child(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
    agents: list[Agent] | None = None,
) -> ActionResult:
    """Feed a child agent: reduce child's hunger by 30, consume 1 berry from caregiver."""
    if step is None or not step.get("child_id"):
        return ActionResult(
            success=False,
            action_type=ActionType.FEED_CHILD,
            action_summary="feed_child_failed: no child_id in step",
            events=[{"type": "feed_child_failed", "reason": "no child_id"}],
        )

    child_id = step["child_id"]
    if not agents:
        return ActionResult(
            success=False,
            action_type=ActionType.FEED_CHILD,
            action_summary="feed_child_failed: no agents available",
            events=[{"type": "feed_child_failed", "reason": "no agents"}],
        )

    child = next((a for a in agents if a.id == child_id), None)
    if not child:
        return ActionResult(
            success=False,
            action_type=ActionType.FEED_CHILD,
            action_summary="feed_child_failed: child not found",
            events=[{"type": "feed_child_failed", "reason": "child not found"}],
        )

    # Child must be within interaction radius (3 tiles)
    dist = ((agent.position[0] - child.position[0]) ** 2 + (agent.position[1] - child.position[1]) ** 2) ** 0.5
    if dist > 3.0:
        return ActionResult(
            success=False,
            action_type=ActionType.FEED_CHILD,
            action_summary="feed_child_failed: child too far",
            events=[{"type": "feed_child_failed", "reason": "child too far"}],
        )

    if agent.inventory.get("berries", 0) <= 0:
        return ActionResult(
            success=False,
            action_type=ActionType.FEED_CHILD,
            action_summary="feed_child_failed: no berries",
            events=[{"type": "feed_child_failed", "reason": "no berries"}],
        )

    agent.inventory["berries"] -= 1
    child.hunger = max(0.0, child.hunger - 30)

    return ActionResult(
        success=True,
        action_type=ActionType.FEED_CHILD,
        action_summary=f"fed {child.name}: hunger:-30, berries:-1",
        events=[{"type": "feed_child", "child_id": child_id}],
        state_changes={"hunger": child.hunger, "inventory": dict(agent.inventory)},
    )


def handle_mine(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Mine a nearby mineral tile (stone or iron_ore), adding ore to inventory."""
    for x, y, tile in _tiles_on_or_adjacent(agent, world):
        if tile.resource_type in ("stone", "iron_ore") and tile.amount > 0:
            key = tile.resource_type
            if not _inventory_capacity(agent, key):
                return ActionResult(
                    success=False,
                    action_type=ActionType.MINE,
                    action_summary="mine_failed: inventory full",
                    events=[{"type": "mine_failed", "reason": "inventory full"}],
                )
            tile.amount = max(0, tile.amount - 1)
            agent.inventory[key] = agent.inventory.get(key, 0) + 1

            if tile.amount == 0:
                tile.resource_type = None

            world.set_tile(x, y, tile)
            return ActionResult(
                success=True,
                action_type=ActionType.MINE,
                action_summary=f"{key}:+1",
                events=[{"type": "mine", "resource": key, "amount": 1}],
                state_changes={"inventory": dict(agent.inventory)},
            )

    return ActionResult(
        success=False,
        action_type=ActionType.MINE,
        action_summary="mine_failed: no mineral nearby",
        events=[{"type": "mine_failed", "reason": "no mineral nearby"}],
    )


def handle_explore(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Move agent one step toward the nearest unexplored tile.

    Records the agent's current position in *explored_tiles* before moving.
    """
    cx, cy = _agent_grid_pos(agent)
    agent.explored_tiles.add((cx, cy))

    # Find nearest unexplored tile via BFS
    nearest = None
    visited = {(cx, cy)}
    queue = [(cx, cy, [])]

    while queue:
        x, y, path = queue.pop(0)
        if (x, y) not in agent.explored_tiles and (x, y) != (cx, cy):
            nearest = path + [(x, y)] if not path else path
            break
        for nx, ny in world.get_neighbors(x, y):
            if (nx, ny) not in visited:
                visited.add((nx, ny))
                queue.append((nx, ny, path + [(nx, ny)]))

    if not nearest:
        return ActionResult(
            success=False,
            action_type=ActionType.EXPLORE,
            action_summary="explore_failed: no unexplored tiles",
            events=[{"type": "explore_failed", "reason": "no unexplored tiles"}],
        )

    # Move one step toward the nearest unexplored tile
    next_pos = nearest[0]
    agent.position = (float(next_pos[0]), float(next_pos[1]))
    agent.explored_tiles.add(next_pos)

    return ActionResult(
        success=True,
        action_type=ActionType.EXPLORE,
        action_summary=f"explored:{next_pos}",
        events=[{"type": "explore", "position": next_pos}],
        state_changes={"position": agent.position, "explored_tiles": set(agent.explored_tiles)},
    )


def handle_craft(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Craft an item using the recipe specified in *step['recipe']*."""
    if step is None or not step.get("recipe"):
        return ActionResult(
            success=False,
            action_type=ActionType.CRAFT,
            action_summary="craft_failed: no recipe specified",
            events=[{"type": "craft_failed", "reason": "no recipe"}],
        )

    from app.simulation.crafting import CraftingManager

    recipe_name = step["recipe"]
    return CraftingManager.craft(agent, recipe_name, world)


def handle_hunt(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Hunt an animal on an adjacent tile.

    Requires a weapon (spear or bow) in inventory.
    If using a bow, requires at least 1 arrow.
    Yields meat and hide on success.
    """
    # Determine weapon
    weapon = None
    if agent.inventory.get("bow", 0) > 0:
        weapon = "bow"
    elif agent.inventory.get("spear", 0) > 0:
        weapon = "spear"

    if weapon is None:
        return ActionResult(
            success=False,
            action_type=ActionType.HUNT,
            action_summary="hunt_failed: no weapon",
            events=[{"type": "hunt_failed", "reason": "no weapon"}],
        )

    if weapon == "bow" and agent.inventory.get("arrows", 0) <= 0:
        return ActionResult(
            success=False,
            action_type=ActionType.HUNT,
            action_summary="hunt_failed: no arrows",
            events=[{"type": "hunt_failed", "reason": "no arrows"}],
        )

    # Find animal in adjacent tiles
    for x, y, tile in _tiles_on_or_adjacent(agent, world):
        if tile.resource_type in ("deer", "rabbit", "boar") and tile.amount > 0:
            if not _inventory_capacity(agent, "meat") or not _inventory_capacity(agent, "hide"):
                return ActionResult(
                    success=False,
                    action_type=ActionType.HUNT,
                    action_summary="hunt_failed: inventory full",
                    events=[{"type": "hunt_failed", "reason": "inventory full"}],
                )
            tile.amount = max(0, tile.amount - 1)
            if tile.amount == 0:
                tile.resource_type = None
            world.set_tile(x, y, tile)

            # Yields
            meat_yield = 1
            hide_yield = 1

            agent.inventory["meat"] = agent.inventory.get("meat", 0) + meat_yield
            agent.inventory["hide"] = agent.inventory.get("hide", 0) + hide_yield

            if weapon == "bow":
                agent.inventory["arrows"] -= 1
                if agent.inventory["arrows"] == 0:
                    del agent.inventory["arrows"]

            return ActionResult(
                success=True,
                action_type=ActionType.HUNT,
                action_summary=f"hunted {tile.resource_type or 'animal'}: meat:+{meat_yield}, hide:+{hide_yield}",
                events=[{"type": "hunt", "meat": meat_yield, "hide": hide_yield}],
                state_changes={"inventory": dict(agent.inventory)},
            )

    return ActionResult(
        success=False,
        action_type=ActionType.HUNT,
        action_summary="hunt_failed: no animal nearby",
        events=[{"type": "hunt_failed", "reason": "no animal nearby"}],
    )


def handle_fish(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Fish from an adjacent water tile. Requires a fishing rod."""
    if agent.inventory.get("fishing_rod", 0) <= 0:
        return ActionResult(
            success=False,
            action_type=ActionType.FISH,
            action_summary="fish_failed: no fishing_rod",
            events=[{"type": "fish_failed", "reason": "no fishing_rod"}],
        )

    for x, y, tile in _tiles_on_or_adjacent(agent, world):
        if tile.resource_type == "water":
            if not _inventory_capacity(agent, "fish"):
                return ActionResult(
                    success=False,
                    action_type=ActionType.FISH,
                    action_summary="fish_failed: inventory full",
                    events=[{"type": "fish_failed", "reason": "inventory full"}],
                )
            agent.inventory["fish"] = agent.inventory.get("fish", 0) + 1
            return ActionResult(
                success=True,
                action_type=ActionType.FISH,
                action_summary="fish:+1",
                events=[{"type": "fish", "amount": 1}],
                state_changes={"inventory": dict(agent.inventory)},
            )

    return ActionResult(
        success=False,
        action_type=ActionType.FISH,
        action_summary="fish_failed: no water nearby",
        events=[{"type": "fish_failed", "reason": "no water nearby"}],
    )


def handle_attack(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
    agents: list[Agent] | None = None,
) -> ActionResult:
    """Attack a target agent."""
    if step is None or not step.get("target_agent"):
        return ActionResult(
            success=False,
            action_type=ActionType.ATTACK,
            action_summary="attack_failed: no target_agent in step",
            events=[{"type": "attack_failed", "reason": "no target_agent"}],
        )

    if not agents:
        return ActionResult(
            success=False,
            action_type=ActionType.ATTACK,
            action_summary="attack_failed: no agents available",
            events=[{"type": "attack_failed", "reason": "no agents"}],
        )

    target_id = step["target_agent"]
    target_agent = next((a for a in agents if a.id == target_id), None)
    if not target_agent:
        return ActionResult(
            success=False,
            action_type=ActionType.ATTACK,
            action_summary="attack_failed: target not found",
            events=[{"type": "attack_failed", "reason": "target not found"}],
        )

    if target_agent.id == agent.id:
        return ActionResult(
            success=False,
            action_type=ActionType.ATTACK,
            action_summary="attack_failed: cannot attack self",
            events=[{"type": "attack_failed", "reason": "cannot attack self"}],
        )

    dist = math.hypot(
        agent.position[0] - target_agent.position[0],
        agent.position[1] - target_agent.position[1],
    )

    from app.simulation.combat import CombatManager

    weapon_name = agent.equipment.get("weapon", "fist")
    weapon_stats = CombatManager.get_weapon_stats(weapon_name)
    if not weapon_stats:
        weapon_stats = CombatManager.get_weapon_stats("fist")

    is_ranged = weapon_stats.get("ranged", False)
    max_range = weapon_stats.get("max_range", 3) if is_ranged else 3

    if dist > max_range:
        return ActionResult(
            success=False,
            action_type=ActionType.ATTACK,
            action_summary="attack_failed: target out of range",
            events=[{"type": "attack_failed", "reason": "target out of range"}],
        )

    if is_ranged and weapon_stats.get("ammo"):
        ammo = weapon_stats["ammo"]
        if agent.inventory.get(ammo, 0) <= 0:
            return ActionResult(
                success=False,
                action_type=ActionType.ATTACK,
                action_summary=f"attack_failed: no {ammo}",
                events=[{"type": "attack_failed", "reason": f"no {ammo}"}],
            )
        agent.inventory[ammo] -= 1
        if agent.inventory[ammo] == 0:
            del agent.inventory[ammo]

    armor_name = target_agent.equipment.get("armor", "none")
    armor_stats = CombatManager.get_armor_stats(armor_name)
    armor_reduction = armor_stats.get("damage_reduction", 0)

    weapon_damage = weapon_stats.get("damage", 5)
    if is_ranged:
        damage = CombatManager.calculate_ranged_damage_with_effects(agent, weapon_damage, armor_reduction)
    else:
        damage = CombatManager.calculate_melee_damage_with_effects(agent, weapon_damage, armor_reduction)

    damage = CombatManager.calculate_damage_with_guard(damage, target_agent.is_guarding)
    target_agent.health = max(0.0, target_agent.health - damage)

    # Track combat initiation for downstream systems
    agent._last_combat_target = target_agent.id

    # Track combat death source
    if target_agent.health <= 0:
        target_agent._combat_attacker_id = agent.id

    return ActionResult(
        success=True,
        action_type=ActionType.ATTACK,
        action_summary=f"attacked {target_agent.name}: damage={damage:.1f}",
        events=[{"type": "attack", "target_id": target_agent.id, "damage": damage}],
        state_changes={"damage_dealt": damage, "target_health": target_agent.health},
    )


def handle_guard(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Guard: reduces incoming damage until interrupted."""
    agent.is_guarding = True
    return ActionResult(
        success=True,
        action_type=ActionType.GUARD,
        action_summary="guarding",
        events=[{"type": "guard"}],
        state_changes={"is_guarding": True},
    )


def handle_heal(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Heal self: consume 1 berry, restore 10 + intelligence * 0.1 health."""
    if agent.inventory.get("berries", 0) <= 0:
        return ActionResult(
            success=False,
            action_type=ActionType.HEAL,
            action_summary="heal_failed: no berries",
            events=[{"type": "heal_failed", "reason": "no berries"}],
        )

    agent.inventory["berries"] -= 1
    heal_amount = 10 + agent.intelligence * 0.1
    agent.health = min(100.0, agent.health + heal_amount)

    return ActionResult(
        success=True,
        action_type=ActionType.HEAL,
        action_summary=f"healed: +{heal_amount:.1f} health",
        events=[{"type": "heal", "amount": heal_amount}],
        state_changes={"health": agent.health, "inventory": dict(agent.inventory)},
    )


def handle_build(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Build a structure at the agent's current position."""
    if step is None or not step.get("structure_type"):
        return ActionResult(
            success=False,
            action_type=ActionType.BUILD,
            action_summary="build_failed: no structure_type specified",
            events=[{"type": "build_failed", "reason": "no structure_type"}],
        )

    structure_type = step["structure_type"]
    from app.simulation.structures import STRUCTURE_COSTS, STRUCTURE_DEFINITIONS, Structure

    if structure_type not in STRUCTURE_COSTS:
        return ActionResult(
            success=False,
            action_type=ActionType.BUILD,
            action_summary=f"build_failed: unknown structure_type {structure_type}",
            events=[{"type": "build_failed", "reason": f"unknown {structure_type}"}],
        )

    costs = STRUCTURE_COSTS[structure_type]
    for resource, qty in costs.items():
        if agent.inventory.get(resource, 0) < qty:
            return ActionResult(
                success=False,
                action_type=ActionType.BUILD,
                action_summary=f"build_failed: insufficient {resource}",
                events=[{"type": "build_failed", "reason": f"insufficient {resource}"}],
            )

    # Check tile is empty: no resource, not blocked, no existing structure
    cx, cy = _agent_grid_pos(agent)
    tile = world.get_tile(cx, cy)
    if tile.resource_type is not None or tile.blocked:
        return ActionResult(
            success=False,
            action_type=ActionType.BUILD,
            action_summary="build_failed: tile occupied by resource",
            events=[{"type": "build_failed", "reason": "tile occupied by resource"}],
        )
    if world.structures.get_structure_at((cx, cy)) is not None:
        return ActionResult(
            success=False,
            action_type=ActionType.BUILD,
            action_summary="build_failed: tile occupied by structure",
            events=[{"type": "build_failed", "reason": "tile occupied by structure"}],
        )

    # Deduct materials
    for resource, qty in costs.items():
        agent.inventory[resource] -= qty
        if agent.inventory[resource] == 0:
            del agent.inventory[resource]

    # Create structure
    health = STRUCTURE_DEFINITIONS.get(structure_type, {}).get("health", 100)
    structure_id = f"struct_{structure_type}_{cx}_{cy}"
    structure = Structure(
        id=structure_id,
        structure_type=structure_type,
        position=(cx, cy),
        owner_id=agent.id,
        health=float(health),
        max_health=float(health),
    )
    world.structures.add_structure(structure)

    return ActionResult(
        success=True,
        action_type=ActionType.BUILD,
        action_summary=f"built {structure_type}",
        events=[{"type": "build", "structure_type": structure_type, "structure_id": structure_id}],
        state_changes={"inventory": dict(agent.inventory), "structure_id": structure_id},
    )


def handle_farm(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Farm at an adjacent farm structure."""
    cx, cy = _agent_grid_pos(agent)
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            if dx == 0 and dy == 0:
                continue
            sx, sy = cx + dx, cy + dy
            structure = world.structures.get_structure_at((sx, sy))
            if structure is not None and structure.structure_type == "farm":
                agent.inventory["berries"] = agent.inventory.get("berries", 0) + 3
                agent.inventory["fiber"] = agent.inventory.get("fiber", 0) + 1
                return ActionResult(
                    success=True,
                    action_type=ActionType.FARM,
                    action_summary="farmed: berries:+3, fiber:+1",
                    events=[{"type": "farm", "berries": 3, "fiber": 1}],
                    state_changes={"inventory": dict(agent.inventory)},
                )

    return ActionResult(
        success=False,
        action_type=ActionType.FARM,
        action_summary="farm_failed: no farm nearby",
        events=[{"type": "farm_failed", "reason": "no farm nearby"}],
    )


REGISTRY: dict[ActionType, ActionHandler] = {
    ActionType.MOVE: handle_move,
    ActionType.CHOP: handle_chop,
    ActionType.DRINK: handle_drink,
    ActionType.EAT: handle_eat,
    ActionType.GATHER: handle_gather,
    ActionType.REST: handle_rest,
    ActionType.REPRODUCE: handle_reproduce,
    ActionType.TRADE: handle_trade,
    ActionType.SOCIALIZE: handle_socialize,
    ActionType.FEED_CHILD: handle_feed_child,
    ActionType.MINE: handle_mine,
    ActionType.EXPLORE: handle_explore,
    ActionType.CRAFT: handle_craft,
    ActionType.HUNT: handle_hunt,
    ActionType.FISH: handle_fish,
    ActionType.ATTACK: handle_attack,
    ActionType.GUARD: handle_guard,
    ActionType.HEAL: handle_heal,
    ActionType.BUILD: handle_build,
    ActionType.FARM: handle_farm,
}


def _action_to_skill(action_type: ActionType) -> str | None:
    """Map an action type to its primary skill name. Returns None if unknown."""
    mapping = {
        ActionType.CHOP: "carpentry",
        ActionType.BUILD: "carpentry",
        ActionType.ATTACK: "combat",
        ActionType.HUNT: "survival",
        ActionType.FISH: "survival",
        ActionType.GATHER: "survival",
        ActionType.CRAFT: "crafting",
        ActionType.SOCIALIZE: "social",
        ActionType.TRADE: "social",
        ActionType.EXPLORE: "exploration",
        ActionType.MOVE: "exploration",
        ActionType.MINE: "mining",
        ActionType.FARM: "farming",
    }
    return mapping.get(action_type)


def get_action_duration(action_type: ActionType, agent: Agent, world: World = None) -> int:
    """Return duration in ticks for an action based on agent attributes."""
    durations = {
        ActionType.MOVE: max(1, 10 - agent.speed // 10),
        ActionType.CHOP: max(2, 10 - agent.strength // 10),
        ActionType.DRINK: 3,
        ActionType.EAT: 3,
        ActionType.GATHER: max(2, 5 - agent.speed // 20),
        ActionType.REST: max(3, 20 - int(agent.energy) // 5),
        ActionType.REPRODUCE: 10,
        ActionType.TRADE: 5,
        ActionType.SOCIALIZE: 3,
        ActionType.FEED_CHILD: 3,
        ActionType.MINE: max(3, 10 - agent.strength // 10),
        ActionType.EXPLORE: max(1, 5 - agent.speed // 20),
        ActionType.HUNT: max(3, 8 - agent.strength // 10),
        ActionType.FISH: 5,
        ActionType.CRAFT: 10,
        ActionType.ATTACK: 5,
        ActionType.GUARD: 3,
        ActionType.HEAL: 5,
        ActionType.BUILD: max(5, 15 - agent.strength // 10),
        ActionType.FARM: 5,
    }
    base = durations[action_type]
    # Apply tool modifiers for actions that support them
    if action_type in (ActionType.CHOP, ActionType.MINE):
        base = apply_tool_modifier(agent, action_type, base)

    # Apply skill and effect speed modifiers
    skill_name = _action_to_skill(action_type)
    skill_mod = SkillManager.get_speed_modifier(agent, skill_name) if skill_name else 1.0
    effect_mod = StatusEffectManager.get_total_modifiers(agent).get("speed_multiplier", 1.0)
    emotion_mod = EmotionManager.get_total_modifiers(agent).get("speed_multiplier", 1.0)

    # Weather modifier: compose from World's WeatherSystem if available
    weather_mod = 1.0
    if world is not None and hasattr(world, 'weather'):
        w_def = world.weather._get_current_def()
        if w_def and w_def.effects:
            # Get weather speed effect with shelter protection
            w_effects = world.weather.get_effects_for_agent(
                agent,
                shelter_mult=world.weather._get_agent_shelter(agent, world),
            )
            weather_mod = w_effects.get("speed_multiplier", 1.0)

    return max(1, round(base * skill_mod * effect_mod * emotion_mod * weather_mod))


ACTION_EMOJIS: dict[ActionType, str] = {
    ActionType(name): action_def.emoji
    for name, action_def in DEFINITIONS.actions.items()
}


__all__ = [
    "ActionType",
    "ActionResult",
    "REGISTRY",
    "get_action_duration",
    "ACTION_EMOJIS",
    "apply_tool_modifier",
    "get_item_modifiers",
    "ITEM_MODIFIERS",
    "handle_move",
    "handle_chop",
    "handle_drink",
    "handle_eat",
    "handle_gather",
    "handle_rest",
    "handle_reproduce",
    "handle_mine",
    "handle_explore",
    "handle_craft",
    "handle_hunt",
    "handle_fish",
    "handle_attack",
    "handle_guard",
    "handle_heal",
    "handle_build",
    "handle_farm",
]
