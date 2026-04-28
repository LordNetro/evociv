"""Basic in-memory agent memory system.

Stores experiences as text summaries. In a future iteration this will be
replaced by ChromaDB for vector-based retrieval.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional


@dataclass
class MemoryEntry:
    tick: int
    summary: str
    type: str  # "action", "encounter", "discovery", "thought"


class AgentMemory:
    """Simple in-memory memory per agent. FIFO with max size."""

    def __init__(self, max_per_agent: int = 20):
        self._store: dict[str, list[MemoryEntry]] = defaultdict(list)
        self._max = max_per_agent

    def add(self, agent_id: str, tick: int, summary: str, type: str = "action") -> None:
        """Record a memory for an agent."""
        entry = MemoryEntry(tick=tick, summary=summary, type=type)
        self._store[agent_id].append(entry)
        if len(self._store[agent_id]) > self._max:
            self._store[agent_id].pop(0)

    def add_encounter(self, agent_id: str, tick: int, other_name: str) -> None:
        """Convenience: record an encounter."""
        self.add(agent_id, tick, f"Met {other_name}", type="encounter")

    def add_thought(self, agent_id: str, tick: int, thought: str) -> None:
        """Record agent's own thought/plan."""
        self.add(agent_id, tick, thought, type="thought")

    def get_recent(self, agent_id: str, n: int = 5) -> list[MemoryEntry]:
        """Get last N memories for an agent."""
        entries = self._store.get(agent_id, [])
        return entries[-n:]

    def format_recent(self, agent_id: str, n: int = 5) -> str:
        """Get last N memories formatted as text for prompt injection."""
        entries = self.get_recent(agent_id, n)
        if not entries:
            return "(no recent memories)"
        lines = []
        for e in entries:
            lines.append(f"- [{e.type}] tick {e.tick}: {e.summary}")
        return "\n".join(lines)

    def clear(self, agent_id: Optional[str] = None) -> None:
        """Clear memory for one agent or all."""
        if agent_id:
            self._store.pop(agent_id, None)
        else:
            self._store.clear()
