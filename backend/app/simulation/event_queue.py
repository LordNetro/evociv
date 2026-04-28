"""Event queue, proximity detection, and encounter helpers."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Optional

from app.simulation.agent import Agent
from app.simulation.world import World


@dataclass
class SimEvent:
    """Lightweight event for in-engine use (no ORM dependency)."""

    event_id: str
    type: str  # "encounter", "death", "build", "fight", "discovery", "llm_decision", "resource_depleted"
    severity: str  # "info", "warning", "critical"
    description: str
    agent_ids: list[str] = field(default_factory=list)
    tick: int = 0
    position: Optional[tuple[float, float]] = None
    metadata: Optional[dict] = None


class EventQueue:
    def __init__(self) -> None:
        self._pending: list[SimEvent] = []
        self._last_proximity: dict[frozenset, int] = {}  # Pair cooldown tracking

    def push(
        self,
        event_type: str,
        description: str,
        severity: str = "info",
        agent_ids: list[str] | None = None,
        tick: int = 0,
        position: tuple[float, float] | None = None,
        metadata: dict | None = None,
    ) -> SimEvent:
        """Create and queue a new event."""
        event = SimEvent(
            event_id=f"{event_type}_{uuid.uuid4().hex[:8]}",
            type=event_type,
            severity=severity,
            description=description,
            agent_ids=agent_ids or [],
            tick=tick,
            position=position,
            metadata=metadata,
        )
        self._pending.append(event)
        return event

    def drain(self) -> list[SimEvent]:
        """Return and clear all pending events."""
        events = self._pending
        self._pending = []
        return events

    @property
    def pending_count(self) -> int:
        return len(self._pending)


def check_proximity_encounters(
    agents: list[Agent],
    radius: float = 3.0,
    current_tick: int = 0,
    cooldown_ticks: int = 10,
) -> list[SimEvent]:
    """
    Check all agent pairs for proximity-based encounters.
    Returns list of SimEvent objects for new encounters.
    """
    events: list[SimEvent] = []
    # Simple O(n²) — fine for 10-20 agents
    for i, a1 in enumerate(agents):
        for a2 in agents[i + 1 :]:
            dist = math.hypot(
                a1.position[0] - a2.position[0],
                a1.position[1] - a2.position[1],
            )
            if dist < radius:
                events.append(
                    SimEvent(
                        event_id=f"encounter_{uuid.uuid4().hex[:8]}",
                        type="encounter",
                        severity="info",
                        description=f"{a1.name} encountered {a2.name}",
                        agent_ids=[a1.id, a2.id],
                        tick=current_tick,
                        position=(
                            (a1.position[0] + a2.position[0]) / 2,
                            (a1.position[1] + a2.position[1]) / 2,
                        ),
                    )
                )
    return events


def check_resource_discoveries(
    agent: Agent,
    world: World,
    discovered_set: set[tuple[str, int, int]],
    current_tick: int = 0,
) -> list[SimEvent]:
    """
    Check if agent has discovered a new resource.
    discovered_set tracks (agent_id, x, y) tuples already discovered.
    """
    events: list[SimEvent] = []
    gx, gy = int(agent.position[0]), int(agent.position[1])
    key = (agent.id, gx, gy)

    if key not in discovered_set:
        discovered_set.add(key)
        tile = world.get_tile(gx, gy)
        if tile.resource_type:
            events.append(
                SimEvent(
                    event_id=f"discovery_{uuid.uuid4().hex[:8]}",
                    type="discovery",
                    severity="info",
                    description=f"{agent.name} discovered {tile.resource_type} at ({gx}, {gy})",
                    agent_ids=[agent.id],
                    tick=current_tick,
                    position=(float(gx), float(gy)),
                )
            )
    return events


def create_death_event(agent: Agent, current_tick: int) -> SimEvent:
    return SimEvent(
        event_id=f"death_{uuid.uuid4().hex[:8]}",
        type="death",
        severity="critical",
        description=f"{agent.name} has died",
        agent_ids=[agent.id],
        tick=current_tick,
        position=agent.position,
    )


__all__ = [
    "SimEvent",
    "EventQueue",
    "check_proximity_encounters",
    "check_resource_discoveries",
    "create_death_event",
]
