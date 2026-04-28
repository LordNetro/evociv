"""Action system: types, results, handlers, and registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from app.simulation.agent import Agent
from app.simulation.world import World


class ActionType(str, Enum):
    MOVE = "move"
    CHOP = "chop"
    DRINK = "drink"
    EAT = "eat"
    GATHER = "gather"
    REST = "rest"
    REPRODUCE = "reproduce"


@dataclass
class ActionResult:
    success: bool = True
    events: list[dict] = field(default_factory=list)
    interrupted: bool = False
    state_changes: dict[str, Any] = field(default_factory=dict)


ActionHandler = Callable[
    [Agent, World, Optional[tuple[int, int]], Optional[dict]], ActionResult
]


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
            state_changes={"position": agent.position},
        )

    return ActionResult(
        success=True,
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
            tile.amount = max(0, tile.amount - 1)
            agent.inventory["wood"] = agent.inventory.get("wood", 0) + 1

            if tile.amount == 0:
                tile.resource_type = None

            world.set_tile(x, y, tile)
            return ActionResult(
                success=True,
                events=[{"type": "chop", "resource": "tree", "amount": 1}],
                state_changes={"inventory": dict(agent.inventory)},
            )

    return ActionResult(
        success=False,
        events=[{"type": "chop_failed", "reason": "no tree nearby"}],
    )


def handle_drink(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Drink from a nearby water source, reducing thirst to 0 (fully hydrated)."""
    for x, y, tile in _tiles_on_or_adjacent(agent, world):
        if tile.resource_type == "water":
            agent.thirst = 0.0
            return ActionResult(
                success=True,
                events=[{"type": "drink", "resource": "water"}],
                state_changes={"thirst": agent.thirst},
            )

    return ActionResult(
        success=False,
        events=[{"type": "drink_failed", "reason": "no water nearby"}],
    )


def handle_eat(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Consume one unit of berries from inventory to reduce hunger."""
    if agent.inventory.get("berries", 0) > 0:
        agent.inventory["berries"] -= 1
        agent.hunger = max(0.0, agent.hunger - 20)
        return ActionResult(
            success=True,
            events=[{"type": "eat", "food": "berries"}],
            state_changes={"hunger": agent.hunger, "inventory": dict(agent.inventory)},
        )

    return ActionResult(
        success=False,
        events=[{"type": "eat_failed", "reason": "no food"}],
    )


def handle_gather(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Gather one unit from a nearby berries bush or tree."""
    for x, y, tile in _tiles_on_or_adjacent(agent, world):
        if tile.resource_type in ("berries", "tree") and tile.amount > 0:
            key = "berries" if tile.resource_type == "berries" else "wood"
            tile.amount = max(0, tile.amount - 1)
            agent.inventory[key] = agent.inventory.get(key, 0) + 1

            if tile.amount == 0:
                tile.resource_type = None

            world.set_tile(x, y, tile)
            return ActionResult(
                success=True,
                events=[{"type": "gather", "resource": key, "amount": 1}],
                state_changes={"inventory": dict(agent.inventory)},
            )

    return ActionResult(
        success=False,
        events=[{"type": "gather_failed", "reason": "no gatherable resource nearby"}],
    )


def handle_rest(
    agent: Agent,
    world: World,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Rest in place, recovering energy."""
    agent.energy = min(100.0, agent.energy + 10)
    return ActionResult(
        success=True,
        events=[{"type": "rest", "energy_gained": 10}],
        state_changes={"energy": agent.energy},
    )


def handle_reproduce(
    agent: Agent,
    world: World | None = None,
    target: tuple[int, int] | None = None,
    step: dict | None = None,
) -> ActionResult:
    """Stub — actual reproduction logic is in SimulationEngine."""
    return ActionResult(success=True, events=[{"type": "reproduce"}])


# ---------------------------------------------------------------------------
# Registry & metadata
# ---------------------------------------------------------------------------

REGISTRY: dict[ActionType, ActionHandler] = {
    ActionType.MOVE: handle_move,
    ActionType.CHOP: handle_chop,
    ActionType.DRINK: handle_drink,
    ActionType.EAT: handle_eat,
    ActionType.GATHER: handle_gather,
    ActionType.REST: handle_rest,
    ActionType.REPRODUCE: handle_reproduce,
}


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
    }
    return durations[action_type]


ACTION_EMOJIS: dict[ActionType, str] = {
    ActionType.MOVE: "🚶",
    ActionType.CHOP: "🪓",
    ActionType.DRINK: "💧",
    ActionType.EAT: "🍎",
    ActionType.GATHER: "🫐",
    ActionType.REST: "💤",
    ActionType.REPRODUCE: "❤️",
}


__all__ = [
    "ActionType",
    "ActionResult",
    "REGISTRY",
    "get_action_duration",
    "ACTION_EMOJIS",
    "handle_move",
    "handle_chop",
    "handle_drink",
    "handle_eat",
    "handle_gather",
    "handle_rest",
    "handle_reproduce",
]
