"""Structure system: dataclass, manager, and definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.definitions import DEFINITIONS


@dataclass
class Structure:
    """A built structure in the world."""

    id: str
    structure_type: str
    position: tuple[int, int]
    owner_id: str | None = None
    health: float = 100.0
    max_health: float = 100.0
    properties: dict[str, Any] = field(default_factory=dict)


# Module-level aliases derived from DEFINITIONS for backward compatibility
STRUCTURE_COSTS: dict[str, dict[str, int]] = {
    name: dict(s.costs) for name, s in DEFINITIONS.structures.items()
}
STRUCTURE_DEFINITIONS: dict[str, dict[str, Any]] = {
    name: {
        "health": s.health,
        "passable": s.passable,
        **s.properties,
    }
    for name, s in DEFINITIONS.structures.items()
}


class StructureManager:
    """Manages all structures in the world."""

    def __init__(self) -> None:
        self._structures: dict[str, Structure] = {}
        self._position_index: dict[tuple[int, int], str] = {}

    def add_structure(self, structure: Structure) -> None:
        """Add a structure, replacing any existing one at the same position."""
        # Remove any existing structure at the same position
        old_id = self._position_index.get(structure.position)
        if old_id is not None and old_id != structure.id:
            self._structures.pop(old_id, None)
        self._structures[structure.id] = structure
        self._position_index[structure.position] = structure.id

    def remove_structure(self, structure_id: str) -> None:
        """Remove a structure by ID."""
        structure = self._structures.pop(structure_id, None)
        if structure is not None:
            self._position_index.pop(structure.position, None)

    def get_structure(self, structure_id: str) -> Structure | None:
        """Get a structure by ID."""
        return self._structures.get(structure_id)

    def get_structures_by_owner(self, owner_id: str) -> list[Structure]:
        """Return all structures owned by *owner_id*."""
        return [s for s in self._structures.values() if s.owner_id == owner_id]

    def get_structure_at(self, pos: tuple[int, int]) -> Structure | None:
        """Return the structure at *pos*, or None."""
        sid = self._position_index.get(pos)
        if sid is None:
            return None
        return self._structures.get(sid)

    def list_all(self) -> list[Structure]:
        """Return all structures."""
        return list(self._structures.values())

    def get_nearby_structures(
        self, pos: tuple[int, int], radius: int
    ) -> list[Structure]:
        """Return structures within *radius* (Chebyshev distance) of *pos*."""
        cx, cy = pos
        result: list[Structure] = []
        for s in self._structures.values():
            sx, sy = s.position
            if max(abs(sx - cx), abs(sy - cy)) <= radius:
                result.append(s)
        return result

    def tick_farms(self, agents: list[Any]) -> None:
        """Auto-generate berries for agents near farm structures.

        For each agent within 1 tile of a farm, add 2 berries.
        """
        for agent in agents:
            ax, ay = int(agent.position[0]), int(agent.position[1])
            for s in self._structures.values():
                if s.structure_type == "farm":
                    sx, sy = s.position
                    if max(abs(sx - ax), abs(sy - ay)) <= 1:
                        agent.inventory["berries"] = agent.inventory.get("berries", 0) + 2
                        break
