"""Snapshot builder for simulation state with delta tracking."""

from __future__ import annotations

import time

from app.simulation.world import World
from app.simulation.agent import Agent
from app.simulation.event_queue import SimEvent as EngineEvent
from app.simulation.map_memory import MapMemoryManager
from app.models.schemas import WorldSnapshot, TileUpdate, AgentState, SimulationMetrics, SimEvent as SchemaEvent, StructureUpdate


class WorldSnapshotBuilder:
    """Builds Pydantic schema-compatible snapshots with delta tracking."""

    def __init__(self, world: World, agents: list[Agent]):
        self.world = world
        self.agents = agents
        self._dirty_agents: set[str] = set()    # agent IDs changed since last snapshot
        self._removed_agents: list[str] = []     # agent IDs removed since last snapshot
        self._discovered_set: set[tuple[str, int, int]] = set()  # for resource discovery tracking
        self._dirty_structures: set[str] = set()  # structure IDs changed since last snapshot

    def mark_agent_dirty(self, agent_id: str) -> None:
        """Mark an agent as having changed state."""
        self._dirty_agents.add(agent_id)

    def mark_agent_removed(self, agent_id: str) -> None:
        """Mark an agent as removed (died)."""
        self._removed_agents.append(agent_id)
        self._dirty_agents.discard(agent_id)

    def mark_structure_dirty(self, structure_id: str) -> None:
        """Mark a structure as having changed state."""
        self._dirty_structures.add(structure_id)

    def _build_agent_state(self, agent: Agent, commanded_ids: set[str] | None = None) -> AgentState:
        """Convert an Agent dataclass to a Pydantic AgentState."""
        return AgentState(
            id=agent.id,
            name=agent.name,
            position=agent.position,
            is_commanded=(commanded_ids is not None and agent.id in commanded_ids),
            role=agent.role,
            hunger=round(agent.hunger, 1),
            thirst=round(agent.thirst, 1),
            energy=round(agent.energy, 1),
            health=round(agent.health, 1),
            current_state=agent.fsm_state,
            current_action=agent.current_action,
            current_action_emoji=agent.current_action_emoji or "",
            action_progress=round(agent.action_progress, 2),
            inventory=dict(agent.inventory),
            last_thought=agent.last_thought or "",
            sex=agent.sex,
            age=agent.age,
            max_age=agent.max_age,
            strength=agent.strength,
            intelligence=agent.intelligence,
            sociability=agent.sociability,
            speed=agent.speed,
            system_prompt=agent.system_prompt[:200] if agent.system_prompt else "",
            monologue_history=list(agent.monologue_history[-5:]),
            relationships={
                k: {
                    "interaction_count": v.interaction_count,
                    "last_interaction_tick": v.last_interaction_tick,
                    "score": round(v.score, 2),
                }
                for k, v in agent.relationships.items()
            },
            knowledge=dict(agent.knowledge),
            is_child=agent.is_child,
            parent_id=agent.parent_id,
            faction_id=agent.faction_id,
            current_dialogue=agent.current_dialogue,
            dialogue_type=agent.dialogue_type,
            equipment=dict(agent.equipment),
            skills=dict(agent.skills),
            active_effects={
                name: {
                    "remaining_ticks": data["remaining_ticks"],
                    "current_stacks": data.get("current_stacks", 1),
                }
                for name, data in agent.active_effects.items()
            },
            emotions=dict(agent.emotions),
        )

    def _compute_metrics(self) -> SimulationMetrics:
        """Compute global simulation metrics from all agents."""
        if not self.agents:
            return SimulationMetrics()
        n = len(self.agents)
        return SimulationMetrics(
            population=n,
            avg_hunger=round(sum(a.hunger for a in self.agents) / n, 1),
            avg_thirst=round(sum(a.thirst for a in self.agents) / n, 1),
            avg_health=round(sum(a.health for a in self.agents) / n, 1),
            avg_energy=round(sum(a.energy for a in self.agents) / n, 1),
        )

    def _convert_events(self, engine_events: list[EngineEvent]) -> list[SchemaEvent]:
        """Convert engine SimEvent dataclasses to Pydantic schema events."""
        return [
            SchemaEvent(
                event_id=e.event_id,
                type=e.type,
                severity=e.severity,  # type: ignore
                description=e.description,
                tick=e.tick,
            )
            for e in engine_events
        ]

    def _build_structure_update(self, structure) -> StructureUpdate:
        """Convert a Structure dataclass to a Pydantic StructureUpdate."""
        return StructureUpdate(
            id=structure.id,
            structure_type=structure.structure_type,
            position=structure.position,
            health=round(structure.health, 1),
            max_health=round(structure.max_health, 1),
            owner_id=structure.owner_id,
        )

    def _build_structures_list(self, structure_ids: set[str] | None = None) -> list[StructureUpdate]:
        """Build a list of StructureUpdate objects."""
        structures = []
        for s in self.world.structures.list_all():
            if structure_ids is None or s.id in structure_ids:
                structures.append(self._build_structure_update(s))
        return structures

    def _get_commanded_ids(self, command_queue: dict[str, dict] | None) -> set[str]:
        """Extract set of agent IDs from a command queue dict."""
        if command_queue is None:
            return set()
        return set(command_queue.keys())

    def build(
        self, tick: int, events: list[EngineEvent] | None = None, faction_manager=None,
        colony_stats=None, director_mode: bool = False, command_queue: dict[str, dict] | None = None,
    ) -> WorldSnapshot:
        """
        Build a complete snapshot of the simulation state.
        Includes ALL agents (full state) and ALL tiles (those with resources).
        """
        commanded_ids = self._get_commanded_ids(command_queue)

        # All tiles with resources
        tiles = []
        for y in range(self.world.height):
            for x in range(self.world.width):
                tile = self.world.get_tile(x, y)
                if tile.resource_type:
                    tiles.append(TileUpdate(
                        x=x, y=y,
                        resource_type=tile.resource_type,
                        amount=int(tile.amount),
                        subtype=tile.subtype,
                    ))

        # All agents (full state)
        agents_dict = {}
        for agent in self.agents:
            agents_dict[agent.id] = self._build_agent_state(agent, commanded_ids)

        factions = []
        if faction_manager:
            factions = [
                {
                    "id": f.id,
                    "name": f.name,
                    "color": f.color,
                    "member_count": f.member_count,
                    "shared_resources": f.shared_resources,
                }
                for f in faction_manager.list_all()
            ]

        # Faction tile visibility (fog of war)
        faction_tile_visibility = {}
        if faction_manager:
            for f in faction_manager.get_all().values():
                faction_tile_visibility[f.id] = MapMemoryManager.get_faction_tile_visibility(
                    f, self.world, tick
                )

        removed = list(self._removed_agents)
        self._removed_agents.clear()
        return WorldSnapshot(
            tick=tick,
            timestamp=time.time(),
            tiles=tiles,
            agents=agents_dict,
            removed_agents=removed,
            metrics=self._compute_metrics(),
            events=self._convert_events(events or []),
            factions=factions,
            colony_stats=colony_stats,
            structures=self._build_structures_list(),
            time_state={
                "is_night": self.world.time.is_night,
                "tick_count_of_day": self.world.time.tick_count_of_day,
                "day_count": self.world.time.day_count,
                "day_length_ticks": self.world.time.day_length_ticks,
                "daylight_ticks": self.world.time.daylight_ticks,
                "label": self.world.time.time_of_day_label,
            },
            weather_state=self.world.weather.get_weather_state(),
            faction_tile_visibility=faction_tile_visibility,
            director_mode=director_mode,
        )

    def build_delta(
        self, tick: int, events: list[EngineEvent] | None = None, faction_manager=None,
        colony_stats=None, director_mode: bool = False, command_queue: dict[str, dict] | None = None,
    ) -> WorldSnapshot:
        """
        Build a delta snapshot — only changed data since last call.
        - Tiles: only dirty tiles
        - Agents: ALL agents (state changes every tick anyway)
        - Removed agents: only newly removed
        - Events: only events from this tick
        - Structures: only dirty structures
        """
        commanded_ids = self._get_commanded_ids(command_queue)

        # Dirty tiles
        tiles = []
        for (x, y) in self.world.dirty_tiles:
            tile = self.world.get_tile(x, y)
            tiles.append(TileUpdate(
                x=x, y=y,
                resource_type=tile.resource_type,
                amount=int(tile.amount),
                subtype=tile.subtype,
            ))
        self.world.reset_dirty_tiles()

        # All agents (full state — they change every tick)
        agents_dict = {}
        for agent in self.agents:
            agents_dict[agent.id] = self._build_agent_state(agent, commanded_ids)

        # Removed agents (don't clear here — build() will clear after full snapshot)
        removed = list(self._removed_agents)

        factions = []
        if faction_manager:
            factions = [
                {
                    "id": f.id,
                    "name": f.name,
                    "color": f.color,
                    "member_count": f.member_count,
                    "shared_resources": f.shared_resources,
                }
                for f in faction_manager.list_all()
            ]

        # Dirty structures
        dirty_structures = self._build_structures_list(self._dirty_structures)
        self._dirty_structures.clear()

        # Faction tile visibility (fog of war)
        faction_tile_visibility = {}
        if faction_manager:
            for f in faction_manager.get_all().values():
                faction_tile_visibility[f.id] = MapMemoryManager.get_faction_tile_visibility(
                    f, self.world, tick
                )

        return WorldSnapshot(
            tick=tick,
            timestamp=time.time(),
            tiles=tiles,
            agents=agents_dict,
            removed_agents=removed,
            metrics=self._compute_metrics(),
            events=self._convert_events(events or []),
            factions=factions,
            colony_stats=colony_stats,
            structures=dirty_structures,
            time_state={
                "is_night": self.world.time.is_night,
                "tick_count_of_day": self.world.time.tick_count_of_day,
                "day_count": self.world.time.day_count,
                "day_length_ticks": self.world.time.day_length_ticks,
                "daylight_ticks": self.world.time.daylight_ticks,
                "label": self.world.time.time_of_day_label,
            },
            weather_state=self.world.weather.get_weather_state(),
            faction_tile_visibility=faction_tile_visibility,
            director_mode=director_mode,
        )


__all__ = ["WorldSnapshotBuilder"]
