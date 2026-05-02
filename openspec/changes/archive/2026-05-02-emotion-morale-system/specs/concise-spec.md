# Delta Specs: Emotion/Morale System

## Domain: emotion-system (NEW)

### E1 — Emotion Definitions
System MUST load emotions from `configs/definitions/emotions.yaml`. Each: name, category (positive/negative/neutral), icon, decay_per_tick, effects (attribute→multiplier), triggers (event_type→intensity_delta).

### E2 — Emotional State
Each agent MUST have `emotions: dict[str, dict]` with `{intensity: 0.0–1.0, last_trigger_tick: int}`. Intensity ≤ 0 → auto-removed.

### E3 — Trigger Processing
Events (socialize, eat, combat_win/loss, discovery, faction_event, skill_up) apply intensity delta (clamped 0.0–1.0). Same trigger per agent per emotion: max 1 per 5 ticks.

### E4 — Emotion Decay
`EmotionManager.process_tick()` decrements all intensities by `decay_per_tick`. Different emotions decay at different rates. ≤ 0 → removed.

### E5 — Modifier Aggregation
`get_total_modifiers(agent)` → attribute→multiplier dict. Same attribute: strongest wins (not additive). Formula: `final = skill_mod * status_mod * emotion_mod`.

### E6 — LLM Awareness
Prompt includes `Emotional State: {Dominant} ({intensity}/10), ...`. Dominant emotion first. Empty → "Calm".

## Domain: simulation-engine (MODIFIED)

### E7 — Engine Integration
Tick loop MUST call `EmotionManager.process_tick()` after status effects and before FSM. Action completion triggers emotion events based on type/result.

## Other Modified Domains

| Domain | Change | Trigger |
|--------|--------|---------|
| agent-roles | Agent gains `emotions` field; AgentState snapshot extended | — |
| status-effect-system | Emotion modifiers compose multiplicatively with status effects via same `get_total_modifiers()` | — |
| combat-system | Win → proud; Loss → fearful/sad | `combat_win`, `combat_loss` |
| agent-society | SOCIALIZE → happy/calm; Faction death → sad/angry | `socialize`, `faction_death` |
| skill-system | Level-up → proud/curious | `skill_up` |
