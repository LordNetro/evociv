from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ResourceType(str, Enum):
    TREE = "tree"
    WATER = "water"
    BERRIES = "berries"
    STONE = "stone"


@dataclass
class Tile:
    x: int
    y: int
    resource_type: Optional[str] = None
    amount: int = 0
    max_amount: int = 0
    regen_rate: float = 0.0
    blocked: bool = False


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
        """Check if a tile is within bounds and not blocked."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        return not self.grid[y][x].blocked

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
        """Place resources at random positions using the seed."""
        rng = random.Random(self._seed)
        empty_tiles = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
        ]
        rng.shuffle(empty_tiles)

        # Trees: ~80, amount 5-15 each, regen_rate 0.01
        self._place_resource(
            empty_tiles, ResourceType.TREE, count=80, amount_range=(5, 15), regen_rate=0.01, rng=rng
        )

        # Water: ~15, amount 100, regen_rate 0
        self._place_resource(
            empty_tiles, ResourceType.WATER, count=15, amount_range=(100, 100), regen_rate=0.0, rng=rng
        )

        # Berries: ~40, amount 3-8 each, regen_rate 0.05
        self._place_resource(
            empty_tiles, ResourceType.BERRIES, count=40, amount_range=(3, 8), regen_rate=0.05, rng=rng
        )

        # Stone: ~20, amount 10-30 each, regen_rate 0
        self._place_resource(
            empty_tiles, ResourceType.STONE, count=20, amount_range=(10, 30), regen_rate=0.0, rng=rng
        )

    def _place_resource(
        self,
        available: list[tuple[int, int]],
        resource_type: ResourceType,
        count: int,
        amount_range: tuple[int, int],
        regen_rate: float,
        rng: random.Random,
    ) -> None:
        """Place a resource on up to `count` tiles from `available`."""
        placed = 0
        while placed < count and available:
            x, y = available.pop()
            amount = rng.randint(*amount_range)
            tile = Tile(
                x=x,
                y=y,
                resource_type=resource_type.value,
                amount=amount,
                max_amount=amount,
                regen_rate=regen_rate,
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
