import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.core.config import settings
from app.db.database import engine, Base, async_session_maker
from app.db import models  # noqa: F401 — registers ORM models with Base.metadata
from app.api.ws import router as ws_router, manager as ws_manager
from app.simulation.world import World
from app.simulation.agent import AgentFactory
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
    world = World(width=50, height=50, seed=42)
    agents = AgentFactory.create_default_agents()

    # Attach system prompts from world config (default prompts for now)
    prompts = {
        "agent_001": "You are a gatherer. You prioritize finding food and water. strength=60, intelligence=40, sociability=50, speed=55",
        "agent_002": "You are a builder. You believe in creating shelters and structures. strength=70, intelligence=55, sociability=40, speed=35",
        "agent_003": "You are a scout. You are curious and eager to explore. strength=45, intelligence=60, sociability=65, speed=80",
    }
    for agent in agents:
        agent.system_prompt = prompts.get(agent.id, "")

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
    if engine is None:
        return {"status": "initializing", "tick_rate": settings.tick_rate, "engine_running": False}
    return {
        "status": "ok",
        "tick_rate": settings.tick_rate,
        "engine_running": engine.running,
        "tick": engine.tick_count,
        "agents": len(engine.agents),
        "paused": engine.is_paused,
    }
