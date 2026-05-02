from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.core.definitions import DEFINITIONS
from app.simulation.structures import StructureManager
from app.simulation.time import TimeSystem
from app.simulation.weather import WeatherSystem
from app.simulation.agent import Agent


class ResourceType(str, Enum):
    TREE = "tree"
    WATER = "water"
    BERRIES = "berries"
    STONE = "stone"
    IRON = "iron_ore"
    CLAY = "clay"
    SAND = "sand"
    FIBER = "fiber"


@dataclass
class Tile:
    x: int
    y: int
    resource_type: Optional[str] = None
    amount: int = 0
    max_amount: int = 0
    regen_rate: float = 0.0
    blocked: bool = False
    subtype: Optional[str] = None
    hidden_properties: dict = field(default_factory=dict)


class World:
    """2D grid world with tile-based resources and BFS pathfinding."""

    def __init__(self, width: int = 50, height: int = 50, seed: int = 42):
        self.width = width
        self.height = height
        self._seed = seed
        self.grid: list[list[Tile]] = [
            [Tile(x=x, y=y) for x in range(width)] for y in range(height)
        ]
        self.dirty_tiles: set[tuple[int, int]] = set()
        self.structures = StructureManager()
        self.time = TimeSystem()
        self.weather = WeatherSystem()
        self.generate_initial_resources()

    def get_tile(self, x: int, y: int) -> Tile:
        """O(1) tile access with bounds handling."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"Coordinates ({x}, {y}) out of bounds ({self.width}x{self.height})")
        return self.grid[y][x]

    def set_tile(self, x: int, y: int, tile: Tile) -> None:
        """Update a tile and mark it dirty."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"Coordinates ({x}, {y}) out of bounds ({self.width}x{self.height})")
        self.grid[y][x] = tile
        self.dirty_tiles.add((x, y))

    def is_passable(self, x: int, y: int) -> bool:
        """Check if a tile is within bounds and not blocked by terrain or structure."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        if self.grid[y][x].blocked:
            return False
        structure = self.structures.get_structure_at((x, y))
        if structure is not None:
            from app.simulation.structures import STRUCTURE_DEFINITIONS
            if not STRUCTURE_DEFINITIONS.get(structure.structure_type, {}).get("passable", True):
                return False
        return True

    def get_neighbors(self, x: int, y: int) -> list[tuple[int, int]]:
        """Return 4-directional passable neighbors (up, down, left, right)."""
        candidates = [(x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)]
        return [(nx, ny) for nx, ny in candidates if self.is_passable(nx, ny)]

    def find_path(self, start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
        """BFS shortest path. Returns list of (x, y) waypoints (excluding start, including end)."""
        if start == end:
            return []
        if not self.is_passable(*end):
            return []

        visited = {start}
        queue = deque([(start, [])])

        while queue:
            (cx, cy), path = queue.popleft()
            for nx, ny in self.get_neighbors(cx, cy):
                if (nx, ny) == end:
                    return path + [(nx, ny)]
                if (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append(((nx, ny), path + [(nx, ny)]))
        return []

    def generate_initial_resources(self) -> None:
        """Place resources at random positions using parameters from DEFINITIONS."""
        rng = random.Random(self._seed)
        empty_tiles = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
        ]
        rng.shuffle(empty_tiles)

        # Map from DEFINITIONS resource names to tile resource type strings
        tile_map = {
            "wood": "tree",
            "water": "water",
            "berries": "berries",
            "stone": "stone",
            "iron_ore": "iron_ore",
            "clay": "clay",
            "sand": "sand",
            "fiber": "fiber",
            "deer": "deer",
            "rabbit": "rabbit",
            "boar": "boar",
        }

        # Place resources based on DEFINITIONS data
        for res_name, res_def in DEFINITIONS.resources.items():
            tile_type = tile_map.get(res_name)
            if tile_type is None:
                continue  # Not a placable tile resource (crafted, subproduct)
            props = res_def.properties
            count = props.get("count")
            if count is None:
                continue  # No generation params for this resource
            min_amt = props.get("min_amount", 1)
            max_amt = props.get("max_amount", 1)
            regen = props.get("regen_rate", 0.0)
            self._place_resource(
                empty_tiles, tile_type, count=count,
                amount_range=(min_amt, max_amt), regen_rate=regen, rng=rng,
            )

    def _place_resource(
        self,
        available: list[tuple[int, int]],
        resource_type: ResourceType | str,
        count: int,
        amount_range: tuple[int, int],
        regen_rate: float,
        rng: random.Random,
    ) -> None:
        """Place a resource on up to `count` tiles from `available`."""
        placed = 0
        rt_value = resource_type.value if isinstance(resource_type, ResourceType) else resource_type
        while placed < count and available:
            x, y = available.pop()
            amount = rng.randint(*amount_range)
            subtype = None
            hidden_properties = {}
            if resource_type == ResourceType.BERRIES:
                if rng.random() < 0.3:
                    subtype = "POISONOUS_BERRY"
                    hidden_properties = {"is_poisonous": True}
                else:
                    subtype = "SAFE_BERRY"
                    hidden_properties = {"is_poisonous": False}
            tile = Tile(
                x=x,
                y=y,
                resource_type=rt_value,
                amount=amount,
                max_amount=amount,
                regen_rate=regen_rate,
                subtype=subtype,
                hidden_properties=hidden_properties,
            )
            self.grid[y][x] = tile
            self.dirty_tiles.add((x, y))
            placed += 1

    def regenerate_resources(self) -> None:
        """Slowly replenish resources each tick, capped at max_amount."""
        for y in range(self.height):
            for x in range(self.width):
                tile = self.grid[y][x]
                if tile.resource_type and tile.regen_rate > 0 and tile.amount < tile.max_amount:
                    tile.amount = min(tile.max_amount, tile.amount + tile.regen_rate)
                    self.dirty_tiles.add((x, y))

    def get_nearby_resources(
        self, pos: tuple[float, float], radius: int = 5
    ) -> list[tuple[int, int, str, int]]:
        """Return list of (x, y, resource_type, amount) within radius of pos."""
        cx, cy = int(pos[0]), int(pos[1])
        results: list[tuple[int, int, str, int]] = []
        for y in range(max(0, cy - radius), min(self.height, cy + radius + 1)):
            for x in range(max(0, cx - radius), min(self.width, cx + radius + 1)):
                tile = self.grid[y][x]
                if tile.resource_type:
                    results.append((x, y, tile.resource_type, tile.amount))
        return results

    def reset_dirty_tiles(self) -> None:
        """Clear the dirty tile tracking set."""
        self.dirty_tiles.clear()

    def advance_time(self, agents: list[Agent], tick: int | None = None) -> dict:
        """Advance time and weather by one tick.

        Calls ``TimeSystem.tick()`` and ``WeatherSystem.tick()``, applying
        weather effects (status effects + emotion triggers) to all agents.

        Args:
            agents: List of agents to apply weather effects to.
            tick: Current simulation tick number (for emotion cooldowns).

        Returns:
            A dict with weather change info:
            ``{"weather_changed": bool, "previous": str, "current": str}``
        """
        self.time.tick()
        weather_changes = self.weather.tick(agents=agents, world=self, tick=tick)
        return weather_changes
