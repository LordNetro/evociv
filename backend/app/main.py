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
              system_prompt="You are Zog, a resourceful gatherer. You prioritize finding food and water. You are cautious but reliable."),
        Agent(id="agent_002", name="Mila", position=(20.0, 18.0), role="builder", sex="female",
              strength=70, intelligence=55, sociability=40, speed=35,
              system_prompt="You are Mila, a skilled builder. You believe civilization needs strong shelters and structures. You are patient and methodical."),
        Agent(id="agent_003", name="Kael", position=(22.0, 5.0), role="scout", sex="male",
              strength=45, intelligence=60, sociability=65, speed=80,
              system_prompt="You are Kael, an adventurous scout. You are curious about the world and eager to explore. You are quick and observant."),
        Agent(id="agent_004", name="Nyx", position=(8.0, 20.0), role="gatherer", sex="female",
              strength=40, intelligence=70, sociability=30, speed=60,
              system_prompt="You are Nyx, a perceptive gatherer. You trust few but are loyal to those you befriend. You prefer working alone."),
        Agent(id="agent_005", name="Riv", position=(12.0, 12.0), role="scout", sex="female",
              strength=35, intelligence=50, sociability=80, speed=75,
              system_prompt="You are Riv, a swift scout. You are energetic, talkative, and always looking for new resources to share with the group."),
        Agent(id="agent_006", name="Fen", position=(5.0, 22.0), role="builder", sex="male",
              strength=80, intelligence=45, sociability=55, speed=30,
              system_prompt="You are Fen, a strong builder with a creative mind. You dream of grand structures and work hard to make them reality."),
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
