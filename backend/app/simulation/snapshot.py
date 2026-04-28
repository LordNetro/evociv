"""Snapshot builder for simulation state with delta tracking."""

from __future__ import annotations

import time

from app.simulation.world import World
from app.simulation.agent import Agent
from app.simulation.event_queue import SimEvent as EngineEvent
from app.models.schemas import WorldSnapshot, TileUpdate, AgentState, SimulationMetrics, SimEvent as SchemaEvent


class WorldSnapshotBuilder:
    """Builds Pydantic schema-compatible snapshots with delta tracking."""

    def __init__(self, world: World, agents: list[Agent]):
        self.world = world
        self.agents = agents
        self._dirty_agents: set[str] = set()    # agent IDs changed since last snapshot
        self._removed_agents: list[str] = []     # agent IDs removed since last snapshot
        self._discovered_set: set[tuple[str, int, int]] = set()  # for resource discovery tracking

    def mark_agent_dirty(self, agent_id: str) -> None:
        """Mark an agent as having changed state."""
        self._dirty_agents.add(agent_id)

    def mark_agent_removed(self, agent_id: str) -> None:
        """Mark an agent as removed (died)."""
        self._removed_agents.append(agent_id)
        self._dirty_agents.discard(agent_id)

    def _build_agent_state(self, agent: Agent) -> AgentState:
        """Convert an Agent dataclass to a Pydantic AgentState."""
        return AgentState(
            id=agent.id,
            name=agent.name,
            position=agent.position,
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

    def build(self, tick: int, events: list[EngineEvent] | None = None) -> WorldSnapshot:
        """
        Build a complete snapshot of the simulation state.
        Includes ALL agents (full state) and ALL tiles (those with resources).
        """
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
                    ))

        # All agents (full state)
        agents_dict = {}
        for agent in self.agents:
            agents_dict[agent.id] = self._build_agent_state(agent)

        return WorldSnapshot(
            tick=tick,
            timestamp=time.time(),
            tiles=tiles,
            agents=agents_dict,
            removed_agents=list(self._removed_agents),
            metrics=self._compute_metrics(),
            events=self._convert_events(events or []),
        )

    def build_delta(self, tick: int, events: list[EngineEvent] | None = None) -> WorldSnapshot:
        """
        Build a delta snapshot — only changed data since last call.
        - Tiles: only dirty tiles
        - Agents: ALL agents (state changes every tick anyway)
        - Removed agents: only newly removed
        - Events: only events from this tick
        """
        # Dirty tiles
        tiles = []
        for (x, y) in self.world.dirty_tiles:
            tile = self.world.get_tile(x, y)
            tiles.append(TileUpdate(
                x=x, y=y,
                resource_type=tile.resource_type,
                amount=int(tile.amount),
            ))
        self.world.reset_dirty_tiles()

        # All agents (full state — they change every tick)
        agents_dict = {}
        for agent in self.agents:
            agents_dict[agent.id] = self._build_agent_state(agent)

        # Removed agents (drain)
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
        )


__all__ = ["WorldSnapshotBuilder"]
