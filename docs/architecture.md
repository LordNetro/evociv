# Evociv — Architecture Overview

> **Version:** 1.0.0
> **Last Updated:** 2026-04-28
> **Domain:** [evociv.io](https://evociv.io)

---

## System Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    FRONTEND (SvelteKit)                     │
│  ┌──────────┐  ┌───────────┐  ┌────────────────────────┐  │
│  │  Canvas   │  │  UI Panels│  │     Stores (Svelte)     │  │
│  │  Engine   │  │  (HUD,    │  │  ┌──────────────────┐  │  │
│  │  (2D)     │  │  Inspector│  │  │ simulationStore   │  │  │
│  │           │  │  Charts)  │  │  │ uiStore           │  │  │
│  │ - Grid    │  │           │  │  │ configStore       │  │  │
│  │ - Agents  │  │           │  │  └──────────────────┘  │  │
│  │ - Effects │  │           │  │                        │  │
│  └─────┬─────┘  └───────────┘  └───────────┬────────────┘  │
│        │                                    │               │
│        └──────────────┬─────────────────────┘               │
│                       │ WebSocket                            │
└───────────────────────┼──────────────────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────────────────┐
│                   BACKEND (FastAPI)                          │
│  ┌────────────────────┴───────────────────────────────┐     │
│  │              WebSocket Manager                      │     │
│  │  - Broadcast state (every N ticks)                 │     │
│  │  - Receive commands (pause, speed, config)         │     │
│  └────────────────────┬───────────────────────────────┘     │
│                       │                                      │
│  ┌────────────────────┴───────────────────────────────┐     │
│  │              Simulation Engine                      │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │     │
│  │  │  World    │  │  Agents  │  │   Event Queue     │  │     │
│  │  │ (Grid,   │  │ (FSM,   │  │ (Event-Driven AI)  │  │     │
│  │  │ Resources)│  │ State)  │  │                    │  │     │
│  │  └──────────┘  └────┬─────┘  └──────────────────┘  │     │
│  │                     │                                │     │
│  │  ┌──────────────────┴─────────────────────────────┐  │     │
│  │  │            LLM Orchestrator                     │  │     │
│  │  │  (LiteLLM → Ollama / OpenAI / etc)             │  │     │
│  │  └────────────────────────────────────────────────┘  │     │
│  └──────────────────────────────────────────────────────┘     │
│                       │                                      │
│  ┌────────────────────┴───────────────────────────────┐     │
│  │              Storage Layer                          │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │     │
│  │  │  SQLite   │  │ ChromaDB │  │  JSON configs    │  │     │
│  │  │ (Events,  │  │ (Memory  │  │  (Versioned      │  │     │
│  │  │  Metrics) │  │  Vector) │  │   Worlds)        │  │     │
│  │  └──────────┘  └──────────┘  └──────────────────┘  │     │
│  └──────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────┘
```

### Communication

**WebSocket (not REST).** The simulation is real-time state. Every N ticks, the backend sends a delta snapshot of the world. The frontend receives it and renders at 60 FPS with interpolation.

| Channel | Direction | Content |
|---------|-----------|---------|
| `ws://host:port/ws` | Bidirectional | `ServerMessage` / `ClientMessage` |
| Tick → Frontend | Server → Client | `WorldSnapshot` (delta, partial state) |
| Commands | Client → Server | Pause, resume, speed, config changes |

---

## Stack Decisions

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | **SvelteKit** | Fine-grained reactivity. Ideal for live dashboards with many small state updates. |
| 2D Rendering | **Canvas API** + custom interpolation | 10-20 agents initially. Native Canvas avoids PixiJS overhead. Smooth via lerp at 60fps. |
| Communication | **WebSocket** (delta snapshots) | Real-time, low overhead, no polling. |
| Backend | **FastAPI** (Python) | Async, standard for AI/ML integration, LiteLLM compatible. |
| LLM Abstraction | **LiteLLM** | Unified API for Ollama (local), OpenAI, Anthropic. Hot-swappable. |
| Persistence | **SQLite** + **ChromaDB** + **JSON** | Three-layer: relational (events/metrics), vector (agent memory), versioned config (git). |
| AI Trigger | **FSM + Event-Driven** | LLM only on key events. 90% of actions handled by state machine. |

---

## Project Structure

```
evociv/
├── frontend/                  # SvelteKit application
│   ├── src/
│   │   ├── lib/
│   │   │   ├── canvas/        # 2D rendering engine
│   │   │   │   ├── engine.ts      # Game loop, rAF
│   │   │   │   ├── grid.ts        # Tile map renderer
│   │   │   │   ├── entities.ts    # Agent rendering
│   │   │   │   ├── animation.ts   # Lerp, easing, tweens
│   │   │   │   └── camera.ts      # Zoom, pan
│   │   │   ├── components/   # Svelte UI components
│   │   │   ├── stores/       # Svelte stores (simulation, UI, config)
│   │   │   └── types/        # TypeScript types
│   │   └── routes/
│   └── package.json
│
├── backend/                   # FastAPI application
│   ├── app/
│   │   ├── core/              # App config, dependencies
│   │   ├── models/            # Pydantic models
│   │   ├── simulation/        # Simulation engine
│   │   │   ├── engine.py          # Tick loop
│   │   │   ├── agent.py           # Agent entity + FSM
│   │   │   ├── fsm.py             # State machine
│   │   │   ├── actions.py         # Action implementations
│   │   │   └── world.py           # Grid, resources, environment
│   │   ├── ai/                # Intelligence layer
│   │   │   ├── orchestrator.py    # LiteLLM wrapper
│   │   │   ├── prompts.py         # Prompt templates
│   │   │   └── memory.py          # ChromaDB integration
│   │   ├── api/               # REST/WS endpoints
│   │   └── db/                # SQLite models
│   ├── tests/
│   └── requirements.txt
│
├── configs/                   # World configs (git-versioned)
│   └── example-world-01/
│       ├── world.json
│       ├── agents.yaml
│       └── rules.yaml
│
└── docs/                      # Design documentation
    ├── architecture.md
    ├── contracts.md
    └── simulation-loop.md
```

---

## Key Design Decisions

### 1. FSM + Event-Driven AI (CRITICAL)

LLM inference is the bottleneck. Agents do NOT call the LLM every tick.

- **90% of actions** (walking, chopping, drinking, gathering) handled by a Finite State Machine.
- **LLM triggers** only on: `plan_completed`, `critical_need`, `encounter`, `attack`, `discovery`, `external_stimulus`.
- LLM calls are **async and non-blocking** — the simulation continues while waiting.

### 2. Tick Loop Decoupled from Render Loop

- **Backend ticks**: 10 ticks/sec (configurable). Each tick = 100ms of simulation time.
- **Frontend renders**: 60 FPS via `requestAnimationFrame`, interpolating between snapshot states.
- This gives smooth visuals without requiring the backend to run at 60 ticks/sec.

### 3. Three-Layer Storage

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Active state | RAM (Python dicts) | Simulation runs at RAM speed |
| Persistence | SQLite + ChromaDB | Event logs, metrics, agent memories |
| Configuration | JSON/YAML in repo | Worlds are versioned with git |

### 4. Agent Memory (ChromaDB)

Each agent has a vector memory store. Experiences are embedded and stored. When the LLM is triggered, relevant past memories are injected into the prompt context:
> "You remember that yesterday Bob stole your food."

---

## Scalability Notes

- **Initial target**: 10-20 agents. Canvas API is sufficient.
- **Future (50-200 agents)**: Consider PixiJS for WebGL rendering, entity pooling, spatial hashing for collision detection.
- **Future (200+ agents)**: Consider ECS (Entity Component System) architecture, chunked world grid.
