import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.core.config import settings
from app.db.database import engine, Base, async_session_maker
from app.db import models  # noqa: F401 — registers ORM models with Base.metadata
from app.api.ws import router as ws_router, manager as ws_manager
from app.api.colony import router as colony_router
from app.simulation.world import World
from app.simulation.agent import Agent
from app.simulation.engine import SimulationEngine
from app.ai.orchestrator import RealLLMOrchestrator
from app.ai.memory import AgentMemory

# Windows cp1252 can't handle emoji in log output; force UTF-8 for the handler
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure evociv loggers output to console (Uvicorn only shows its own logs by default)
_log_handler = logging.StreamHandler(sys.stdout)
_log_handler.setLevel(logging.INFO)
_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"))
logging.getLogger("evociv").addHandler(_log_handler)

logger = logging.getLogger("evociv")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create simulation engine with real LLM (falls back to MockLLM if unavailable)
    world = World(width=80, height=80, seed=123)

    # 10 agents with diverse roles spread across the 80x80 world
    agents = [
        Agent(id="agent_001", name="Zog", position=(5.0, 5.0), role="gatherer", sex="male",
              strength=60, intelligence=40, sociability=50, speed=55, max_age=3500,
              system_prompt="You are Zog, a gatherer. Gather food (berries) and resources for the tribe. Stay near resource-rich areas. Craft tools when you have materials."),
        Agent(id="agent_002", name="Mila", position=(35.0, 30.0), role="builder", sex="female",
              strength=70, intelligence=55, sociability=40, speed=35, max_age=4000,
              system_prompt="You are Mila, a builder. Construct buildings (houses, walls, workbenches) to develop the settlement. Gather wood and stone first, then build."),
        Agent(id="agent_003", name="Kael", position=(60.0, 10.0), role="scout", sex="male",
              strength=45, intelligence=60, sociability=65, speed=80, max_age=3000,
              system_prompt="You are Kael, a scout. Explore unknown areas and report back. Your speed lets you cover ground quickly. Socialize with other agents to share knowledge."),
        Agent(id="agent_004", name="Nyx", position=(10.0, 50.0), role="hunter", sex="female",
              strength=65, intelligence=50, sociability=30, speed=70, max_age=3200,
              system_prompt="You are Nyx, a hunter. Hunt animals for meat and materials. Craft a spear when you can — it helps with hunting. Stay near animal-rich areas."),
        Agent(id="agent_005", name="Riv", position=(45.0, 60.0), role="fisher", sex="female",
              strength=35, intelligence=50, sociability=80, speed=40, max_age=3500,
              system_prompt="You are Riv, a fisher. Fish from water sources to feed the tribe. Craft a fishing rod when you have materials. Stay near water. Be social!"),
        Agent(id="agent_006", name="Fen", position=(25.0, 70.0), role="farmer", sex="male",
              strength=55, intelligence=60, sociability=45, speed=30, max_age=3800,
              system_prompt="You are Fen, a farmer. Establish farms to produce long-term food. Build farm structures near water. Gather resources to support farming."),
        Agent(id="agent_007", name="Tix", position=(70.0, 55.0), role="miner", sex="male",
              strength=75, intelligence=40, sociability=25, speed=25, max_age=3500,
              system_prompt="You are Tix, a miner. Mine for stone, iron ore, and coal. Craft a pickaxe to mine faster. Provide materials for builders and crafters."),
        Agent(id="agent_008", name="Lia", position=(50.0, 42.0), role="crafter", sex="female",
              strength=40, intelligence=75, sociability=55, speed=35, max_age=3600,
              system_prompt="You are Lia, a crafter. Craft tools, weapons, and equipment for the tribe. Build a workbench first for better recipes. Make axes, pickaxes, spears, armor."),
        Agent(id="agent_009", name="Gor", position=(15.0, 35.0), role="fighter", sex="male",
              strength=80, intelligence=35, sociability=40, speed=50, max_age=3000,
              system_prompt="You are Gor, a fighter. Protect the settlement from threats. Guard important areas. Craft weapons when you have materials. Stay alert."),
        Agent(id="agent_010", name="Ena", position=(40.0, 15.0), role="healer", sex="female",
              strength=30, intelligence=70, sociability=75, speed=45, max_age=4000,
              system_prompt="You are Ena, a healer. Heal injured agents using berries. Stay near the settlement where agents gather. Be social and keep the tribe healthy."),
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
app.include_router(colony_router)


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
