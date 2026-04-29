"""Colony stats REST endpoint."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/api/colony")
async def get_colony_stats(request: Request):
    """Return colony-level statistics."""
    engine = getattr(request.app.state, "engine", None)
    if not engine:
        return {
            "population": 0,
            "births": 0,
            "deaths": 0,
            "role_distribution": {},
            "sex_distribution": {},
            "age_groups": {},
            "total_resources": {},
            "factions": [],
        }
    stats = engine.colony_stats_collector.collect(
        engine.agents, engine.faction_manager
    )
    return {
        "population": stats.population,
        "births": stats.births,
        "deaths": stats.deaths,
        "role_distribution": stats.role_distribution,
        "sex_distribution": stats.sex_distribution,
        "age_groups": stats.age_groups,
        "total_resources": stats.total_resources,
        "factions": stats.factions,
    }
