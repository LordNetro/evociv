"""Colony statistics collector."""

from __future__ import annotations

from dataclasses import dataclass

from app.simulation.agent import Agent


@dataclass
class ColonyStats:
    population: int
    births: int
    deaths: int
    role_distribution: dict[str, int]
    sex_distribution: dict[str, int]
    age_groups: dict[str, int]
    total_resources: dict[str, int]
    factions: list[dict]


class ColonyStatsCollector:
    def __init__(self) -> None:
        self.births = 0
        self.deaths = 0

    def record_birth(self) -> None:
        self.births += 1

    def record_death(self) -> None:
        self.deaths += 1

    def collect(
        self, agents: list[Agent], faction_manager=None
    ) -> ColonyStats:
        role_distribution: dict[str, int] = {}
        sex_distribution: dict[str, int] = {}
        age_groups: dict[str, int] = {"child": 0, "adult": 0, "elder": 0}
        total_resources: dict[str, int] = {}

        for agent in agents:
            role_distribution[agent.role] = role_distribution.get(agent.role, 0) + 1
            sex_distribution[agent.sex] = sex_distribution.get(agent.sex, 0) + 1

            if agent.is_child:
                age_groups["child"] += 1
            elif agent.age > agent.max_age * 0.7:
                age_groups["elder"] += 1
            else:
                age_groups["adult"] += 1

            for res, qty in agent.inventory.items():
                total_resources[res] = total_resources.get(res, 0) + qty

        # Include faction shared_resources in total
        if faction_manager:
            for faction in faction_manager.get_all().values():
                for res, qty in faction.shared_resources.items():
                    total_resources[res] = total_resources.get(res, 0) + qty

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

        return ColonyStats(
            population=len(agents),
            births=self.births,
            deaths=self.deaths,
            role_distribution=role_distribution,
            sex_distribution=sex_distribution,
            age_groups=age_groups,
            total_resources=total_resources,
            factions=factions,
        )


__all__ = ["ColonyStats", "ColonyStatsCollector"]
