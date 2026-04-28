# 🌍 Evociv

> **Civilization Simulator — Powered by Local LLMs**
> *[evociv.io](https://evociv.io)*

Evociv is a 2D sandbox simulation where AI-driven agents build a society — or perish trying. Starting from a small group of humans, watch as they collaborate, compete, manage resources, and develop emergent behaviors, all driven by local Large Language Models.

---

## ✨ Core Features

- **AI-Driven Agents**: Each agent is autonomous, powered by local LLMs (via Ollama) with unique personalities, goals, and relationships.
- **Event-Driven Intelligence**: Agents use a Finite State Machine for routine actions. The LLM is consulted only for meaningful decisions — encounters, discoveries, critical needs.
- **Visible Consciousness**: Click any agent to see their internal monologue, inventory, stats, and relationships in real time.
- **Live Analytics**: Track population, economy, hunger, and thirst through real-time charts.
- **Open & Transparent**: Everything is visible. Every decision, every thought, every interaction.

---

## 🏗️ Architecture

```
Frontend (SvelteKit)  ◄──WebSocket──►  Backend (FastAPI)
     │                                     │
  Canvas API (2D)                    Simulation Engine
  + Interpolation                    + FSM + Event-Driven AI
     │                                     │
  UI Panels                          LiteLLM (Ollama/OpenAI)
  + Charts                            + ChromaDB (Memory)
```

| Layer | Technology |
|-------|-----------|
| Frontend | **SvelteKit** — fine-grained reactivity for live dashboards |
| 2D Rendering | **Canvas API** + custom interpolation (smooth 60 FPS) |
| Communication | **WebSocket** — delta snapshots in real time |
| Backend | **FastAPI** (Python) — async, AI-native |
| LLM Layer | **LiteLLM** — Ollama, OpenAI, Anthropic (hot-swappable) |
| Persistence | **SQLite** (events) + **ChromaDB** (memory) + **JSON** (configs) |

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System overview, stack decisions, project structure |
| [Data Contracts](docs/contracts.md) | WebSocket messages, data models, SQLite schema |
| [Simulation Loop](docs/simulation-loop.md) | FSM details, tick loop, LLM integration |

---

## 🚀 Getting Started

*Coming soon — initial setup instructions.*

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.
