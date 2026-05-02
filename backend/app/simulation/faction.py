"""Faction system: groups, shared resources, and management."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.core.definitions import DEFINITIONS
from app.simulation.agent import Agent


@dataclass
class FactionSummary:
    id: str
    name: str
    color: str
    member_count: int
    shared_resources: dict[str, int]


@dataclass
class Faction:
    id: str
    name: str
    color: str  # hex, e.g. "#FF0000"
    member_ids: list[str] = field(default_factory=list)
    shared_resources: dict[str, int] = field(default_factory=dict)
    shared_tile_memory: dict = field(default_factory=dict)
    tile_reported_by: dict = field(default_factory=dict)


class FactionManager:
    def __init__(self) -> None:
        self.factions: dict[str, Faction] = {}
        self._create_from_definitions()

    def _create_from_definitions(self) -> None:
        """Create factions from DEFINITIONS.factions."""
        for name, faction_def in DEFINITIONS.factions.items():
            self.create(name, faction_def.color)

    def create(self, name: str, color: str) -> Faction:
        """Create a new faction."""
        faction = Faction(
            id=f"faction_{uuid.uuid4().hex[:6]}",
            name=name,
            color=color,
        )
        self.factions[faction.id] = faction
        return faction

    def delete(self, faction_id: str) -> bool:
        """Delete a faction. Returns True if deleted."""
        if faction_id in self.factions:
            del self.factions[faction_id]
            return True
        return False

    def join(self, agent_id: str, faction_id: str) -> bool:
        """Add an agent to a faction."""
        faction = self.factions.get(faction_id)
        if not faction:
            return False
        if agent_id not in faction.member_ids:
            faction.member_ids.append(agent_id)
        return True

    def leave(self, agent_id: str, faction_id: str) -> bool:
        """Remove an agent from a faction."""
        faction = self.factions.get(faction_id)
        if not faction:
            return False
        if agent_id in faction.member_ids:
            faction.member_ids.remove(agent_id)
        return True

    def list_all(self) -> list[FactionSummary]:
        """Return summaries of all factions."""
        return [
            FactionSummary(
                id=f.id,
                name=f.name,
                color=f.color,
                member_count=len(f.member_ids),
                shared_resources=dict(f.shared_resources),
            )
            for f in self.factions.values()
        ]

    def get_faction(self, faction_id: str) -> Faction | None:
        """Get a faction by ID."""
        return self.factions.get(faction_id)

    def transfer_inventory_on_death(self, agent: Agent) -> None:
        """Transfer an agent's inventory to their faction's shared resources."""
        if not agent.faction_id:
            return
        faction = self.factions.get(agent.faction_id)
        if not faction:
            return
        for resource, amount in agent.inventory.items():
            faction.shared_resources[resource] = (
                faction.shared_resources.get(resource, 0) + amount
            )
        self.leave(agent.id, agent.faction_id)

    def get_all(self) -> dict[str, Faction]:
        """Return all factions dict."""
        return dict(self.factions)


__all__ = ["Faction", "FactionSummary", "FactionManager"]
