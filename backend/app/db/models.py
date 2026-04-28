from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SimEvent(Base):
    __tablename__ = "sim_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tick: Mapped[int] = mapped_column(Integer, index=True)
    agent_id: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now
    )


class TickMetric(Base):
    __tablename__ = "tick_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tick: Mapped[int] = mapped_column(Integer, unique=True)
    population: Mapped[int] = mapped_column(Integer, default=0)
    avg_hunger: Mapped[float] = mapped_column(Float, default=0.0)
    avg_thirst: Mapped[float] = mapped_column(Float, default=0.0)
    avg_health: Mapped[float] = mapped_column(Float, default=0.0)
    avg_energy: Mapped[float] = mapped_column(Float, default=0.0)
    total_wood: Mapped[int] = mapped_column(Integer, default=0)
    total_food: Mapped[int] = mapped_column(Integer, default=0)
    total_stone: Mapped[int] = mapped_column(Integer, default=0)
    total_buildings: Mapped[int] = mapped_column(Integer, default=0)
    deaths_this_tick: Mapped[int] = mapped_column(Integer, default=0)
    births_this_tick: Mapped[int] = mapped_column(Integer, default=0)


class WorldConfig(Base):
    __tablename__ = "world_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utc_now
    )


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String, index=True)
    chroma_id: Mapped[str] = mapped_column(String, unique=True)
    timestamp: Mapped[int] = mapped_column(Integer)
    memory_type: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(Text)
