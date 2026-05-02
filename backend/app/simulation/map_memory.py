"""Map memory system — per-agent tile vision, faction shared memory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.definitions import DEFINITIONS
from app.core.definition_models import NightEffects
from app.simulation.agent import Agent


@dataclass
class TileMemory:
    resource_type: Optional[str] = None
    amount: int = 0
    tick_last_seen: int = 0


class MapMemoryManager:
    """Static methods for map memory management — follows SkillManager pattern."""

    @staticmethod
    def get_vision_radius(agent: Agent, is_night: bool = False, weather_name: str = "") -> int:
        """Compute effective vision radius.

        Base=5, modified by night (visibility_multiplier),
        weather (visibility_multiplier), and survival skill bonus (+1 per 5 levels).
        Clamped to [1, 15].
        """
        base = 5

        # Night modifier
        if is_night:
            night_config = DEFINITIONS.time_config.effects.get("night", NightEffects())
            mult = night_config.visibility_multiplier
            base = max(1, int(base * mult))

        # Weather modifier
        if weather_name:
            w_def = DEFINITIONS.weather.get(weather_name)
            if w_def is not None:
                vis_mult = w_def.visibility_multiplier
                base = max(1, int(base * vis_mult))

        # Survival skill bonus: +1 tile per 5 levels
        from app.simulation.skills import SkillManager
        survival_level = SkillManager.get_skill_level(agent, "survival")
        base += survival_level // 5

        return max(1, min(15, base))

    @staticmethod
    def get_visible_tiles(agent: Agent, world, radius: int) -> list[tuple[int, int]]:
        """Get tiles within Manhattan distance radius of agent position.

        Only returns tiles within world bounds.
        """
        cx, cy = int(agent.position[0]), int(agent.position[1])
        tiles = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if abs(dx) + abs(dy) > radius:
                    continue
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < world.width and 0 <= ny < world.height:
                    tiles.append((nx, ny))
        return tiles

    @staticmethod
    def update_vision(agent: Agent, world, faction_manager, tick: int) -> None:
        """Update agent's tile memory from current position.

        Scans visible tiles, updates agent.tile_memory, marks explored_tiles,
        and syncs new discoveries to faction shared memory.
        """
        # Get vision radius
        is_night = False
        weather_name = ""
        if hasattr(world, "time") and hasattr(world.time, "is_night"):
            is_night = world.time.is_night
        if hasattr(world, "weather"):
            weather_name = world.weather.current_weather

        radius = MapMemoryManager.get_vision_radius(agent, is_night, weather_name)
        visible = MapMemoryManager.get_visible_tiles(agent, world, radius)

        new_discoveries = []
        for x, y in visible:
            tile = world.get_tile(x, y)
            key = (x, y)
            old = agent.tile_memory.get(key)

            # Update if new or changed
            if (old is None
                    or old.resource_type != tile.resource_type
                    or old.amount != tile.amount):

                agent.tile_memory[key] = TileMemory(
                    resource_type=tile.resource_type,
                    amount=tile.amount,
                    tick_last_seen=tick,
                )
                new_discoveries.append(key)

                # Mark tile as explored
                agent.explored_tiles.add(key)

        # Sync new discoveries to faction
        if new_discoveries and agent.faction_id and faction_manager:
            MapMemoryManager._sync_to_faction(agent, faction_manager, new_discoveries)

    @staticmethod
    def _sync_to_faction(agent: Agent, faction_manager, tile_keys: list[tuple[int, int]]) -> None:
        """Sync newly discovered tiles to faction shared memory."""
        faction = faction_manager.get_faction(agent.faction_id)
        if not faction:
            return

        for key in tile_keys:
            memory = agent.tile_memory.get(key)
            if memory:
                faction.shared_tile_memory[key] = memory
                faction.tile_reported_by[key] = agent.id

    @staticmethod
    def get_faction_tile_visibility(faction, world, current_tick: int) -> dict:
        """Get visible and fog tiles for a faction.

        Returns:
            dict with 'visible' (currently in vision) and 'fog' (shared memory)
            tile lists. Currently all tiles are 'fog' — full visible/fog split
            requires agent positions per faction.
        """
        result: dict = {"visible": [], "fog": []}

        for (x, y), memory in faction.shared_tile_memory.items():
            tile_info = {
                "x": x,
                "y": y,
                "resource_type": memory.resource_type,
                "amount": memory.amount,
                "tick_last_seen": memory.tick_last_seen,
            }
            # For now, all faction memory is "fog" (not currently visible unless agent is nearby)
            result["fog"].append(tile_info)

        return result


__all__ = ["TileMemory", "MapMemoryManager"]
