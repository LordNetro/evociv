import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.core.config import settings
from app.db.database import engine, Base, async_session_maker
from app.db import models  # noqa: F401 — registers ORM models with Base.metadata
from app.api.ws import router as ws_router, manager as ws_manager
from app.simulation.world import World
from app.simulation.agent import Agent
from app.simulation.engine import SimulationEngine
from app.ai.orchestrator import RealLLMOrchestrator
from app.ai.memory import AgentMemory

logger = logging.getLogger("evociv")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create simulation engine with real LLM
    world = World(width=25, height=25, seed=123)

    # 6 agents for the 25x25 world
    agents = [
        Agent(id="agent_001", name="Zog", position=(3.0, 3.0), role="gatherer", sex="male",
              strength=60, intelligence=40, sociability=50, speed=55,
              system_prompt="You are Zog, a gatherer. YOUR MISSION: Help the tribe survive and grow. You must gather food (berries), drink water, and rest when tired. If you see a compatible partner, reproduce to grow the population. The civilization MUST expand — this is your highest priority."),
        Agent(id="agent_002", name="Mila", position=(20.0, 18.0), role="builder", sex="female",
              strength=70, intelligence=55, sociability=40, speed=35,
              system_prompt="You are Mila, a builder. YOUR MISSION: Help the tribe survive and grow. Gather resources, eat when hungry, drink when thirsty, rest when tired. Reproduce whenever you can — more tribe members mean a stronger civilization. Growth is everything."),
        Agent(id="agent_003", name="Kael", position=(22.0, 5.0), role="scout", sex="male",
              strength=45, intelligence=60, sociability=65, speed=80,
              system_prompt="You are Kael, a scout. YOUR MISSION: Explore and help the tribe expand. Stay alive: eat berries, drink water, rest. Find a partner and reproduce — new members are essential for the civilization to thrive. The future depends on growth."),
        Agent(id="agent_004", name="Nyx", position=(8.0, 20.0), role="gatherer", sex="female",
              strength=40, intelligence=70, sociability=30, speed=60,
              system_prompt="You are Nyx, a gatherer. YOUR MISSION: Ensure the tribe's survival through gathering. Collect food and water, rest to keep your strength up. Reproduction is key — help create the next generation. The civilization must grow at all costs."),
        Agent(id="agent_005", name="Riv", position=(12.0, 12.0), role="scout", sex="female",
              strength=35, intelligence=50, sociability=80, speed=75,
              system_prompt="You are Riv, a scout. YOUR MISSION: Be social and keep the tribe connected. Gather food and water, rest when low on energy. Find a partner and reproduce — the tribe needs more people to survive and grow. Population growth is the top priority."),
        Agent(id="agent_006", name="Fen", position=(5.0, 22.0), role="builder", sex="male",
              strength=80, intelligence=45, sociability=55, speed=30,
              system_prompt="You are Fen, a builder. YOUR MISSION: Build the tribe's future. Gather resources, eat, drink, and rest to stay strong. Reproduction is vital — create offspring to expand the civilization. A growing population means a thriving society. NEVER stop growing."),
    ]

    memory = AgentMemory()
    llm = RealLLMOrchestrator(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout,
        memory=memory,
    )
    sim_engine = SimulationEngine(
        world=world,
        agents=agents,
        ws_manager=ws_manager,
        db_session_factory=async_session_maker,
        llm_orchestrator=llm,
    )
    app.state.llm = llm
    app.state.memory = memory
    app.state.engine = sim_engine
    await sim_engine.start()
    logger.info("Evociv simulation engine started")

    yield

    # Shutdown: stop simulation engine, dispose DB engine
    await sim_engine.stop()
    await engine.dispose()  # SQLAlchemy engine
    logger.info("Evociv simulation engine stopped")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(ws_router)


@app.get("/health")
async def health(request: Request):
    engine = getattr(request.app.state, "engine", None)
    llm = getattr(request.app.state, "llm", None)
    if engine is None:
        return {"status": "initializing", "tick_rate": settings.tick_rate, "engine_running": False}
    return {
        "status": "ok",
        "tick_rate": settings.tick_rate,
        "engine_running": engine.running,
        "tick": engine.tick_count,
        "agents": len(engine.agents),
        "paused": engine.is_paused,
        "llm": {
            "model": settings.llm_model,
            "available": llm.is_available if llm else None,
            "fallback_to_mock": settings.llm_fallback_to_mock,
        },
    }
