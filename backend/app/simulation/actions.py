"""Action system: types, results, handlers, and registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

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
    TRADE = "trade"
    SOCIALIZE = "socialize"
    FEED_CHILD = "feed_child"


@dataclass
class ActionResult:
    success: bool = True
    events: list[dict] = field(default_factory=list)
    interrupted: bool = False
    state_changes: dict[str, Any] = field(default_factory=dict)
    action_type: ActionType | None = None
    action_summary: str = ""


ActionHandler = Callable[..., ActionResult]


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
    """Rest in place, recovering energy."""
    agent.energy = min(100.0, agent.energy + 10)
    return ActionResult(
        success=True,
        action_type=ActionType.REST,
        action_summary="energy:+10",
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
        ActionType.TRADE: 5,
        ActionType.SOCIALIZE: 3,
        ActionType.FEED_CHILD: 3,
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
    ActionType.TRADE: "🤝",
    ActionType.SOCIALIZE: "💬",
    ActionType.FEED_CHILD: "🍼",
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
