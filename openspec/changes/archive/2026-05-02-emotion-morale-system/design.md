# Design: Emotion/Morale System

## Technical Approach

Mirror `StatusEffectManager` exactly: pure static methods on `EmotionManager`, data-driven via `emotions.yaml` → `EmotionDef` Pydantic model, new `Agent.emotions` dict field, tick decay in engine loop, modifier aggregation composited multiplicatively with skills + status effects. Emotions use float intensity (0.0–1.0) with configurable per-tick decay, triggered by game events that add delta. 5-tick cooldown per emotion per agent prevents trigger spam.

## Architecture Decisions

### Decision: Float Intensity Model vs. Boolean Presence

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Boolean flag per emotion | Simple but no gradation — LLM can't distinguish "slightly happy" from "ecstatic" | ❌ |
| Single mood float (-1 to 1) | Simple but can't model concurrent emotions (happy + fearful = cautious) | ❌ |
| Multiple emotions with float intensity | Richer LLM context, natural decay, concurrent emotions possible | ✅ |

**Rationale**: Multiple concurrent emotions with float intensity gives the LLM more nuanced context and matches the complexity of the StatusEffect system's stacking model.

### Decision: Strongest-Wins Aggregation

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Sum emotions | Angry(0.6) + Fearful(0.4) = absurd damage mods | ❌ |
| Average | Dampens all effects — single strong emotion diluted | ❌ |
| Strongest-wins | Each attribute capped at one emotion's contribution, predictable | ✅ |

**Rationale**: Identical to `StatusEffectManager.get_total_modifiers()` strong-wins rule. Predictable, stack-safe, composable with status effect layer via multiplication.

### Decision: Multiplicative Composition

```
total = base * skill_mod * status_effect_mod * emotion_mod
```

**Rationale**: Existing formula is `base * skill_mod * effect_mod`. Adding `* emotion_mod` preserves the chain. Additive would let emotions dominate on low base values. Emotional modifiers start at ±10–15%, dampening to ±1–3% through multiply chain — safe by default.

### Decision: Trigger Cooldown per Emotion

**Rationale**: Without cooldown, a "win combat → proud" trigger every tick would saturate intensity to 1.0. A 5-tick cooldown per emotion per agent allows multiple different emotions to coexist while preventing a single emotion from being spammed.

## Data Flow

```
Engine Tick
  │
  ├─ EmotionManager.process_tick(agent, tick)
  │   └─ decay each active emotion → remove at 0.0
  │
  ├─ Action completion (engine.py L1224-1232)
  │   └─ EmotionManager.apply_trigger(agent, "on_skill_up", tick)
  │
  ├─ Action handlers (actions.py eat/rest/build)
  │   └─ EmotionManager.apply_trigger(agent, "on_eat", tick)
  │
  ├─ Combat resolution (combat.py)
  │   └─ EmotionManager.apply_trigger(agent, "on_win_combat", tick)
  │
  ├─ Social events (conversation.py detect_encounters)
  │   └─ EmotionManager.apply_trigger(agent, "on_socialize", tick)
  │
  ├─ Faction events (engine.py death/faction growth)
  │   └─ EmotionManager.apply_trigger(agent, "on_faction_death", tick)
  │
  └─ Movement discovery (engine.py or event_queue)
      └─ EmotionManager.apply_trigger(agent, "on_discovery", tick)

Modifier consumers:
  get_action_duration():  base * skill_mod * effect_mod * emotion_mod
  combat damage:          base * skill_mod * effect_mod * emotion_mod
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `configs/definitions/emotions.yaml` | Create | 8 emotions with triggers, effects, decay rates |
| `backend/app/core/definition_models.py` | Modify | Add `EmotionDef` model; add `emotions` field to `DefinitionContainer` |
| `backend/app/core/definitions.py` | Modify | Add `emotions.yaml` to `_YAML_FILES` and `_build_definitions()` |
| `backend/app/simulation/emotions.py` | Create | `EmotionManager` with 5 static methods |
| `backend/app/simulation/agent.py` | Modify | Add `emotions: dict[str, dict] = field(default_factory=dict)` |
| `backend/app/simulation/engine.py` | Modify | `_tick()`: call `EmotionManager.process_tick()`; action completion: trigger `on_skill_up`; faction events: trigger `on_faction_death`/`on_faction_growth` |
| `backend/app/simulation/actions.py` | Modify | `get_action_duration()`: multiply `emotion_mod` into duration; eat/rest/build handlers: trigger after success |
| `backend/app/simulation/combat.py` | Modify | Damage calculations: multiply `emotion_mod`; win/lose paths: trigger |
| `backend/app/simulation/conversation.py` | Modify | `detect_encounters()`: trigger `on_socialize` |
| `backend/app/ai/prompts.py` | Modify | Add `{emotional_state}` to `STATE_PROMPT_TEMPLATE`; inject via `EmotionManager.get_emotional_state_str()` |
| `backend/app/models/schemas.py` | Modify | Add `emotions: dict[str, dict] = {}` to `AgentState` |
| `backend/app/simulation/snapshot.py` | Modify | Add `emotions` to `_build_agent_state()` |
| `backend/tests/test_emotions.py` | Create | Unit tests for all `EmotionManager` methods |

## Interfaces / Contracts

```python
# EmotionDef — definition_models.py
class EmotionDef(BaseModel):
    name: str
    category: str       # "positive" | "negative" | "neutral"
    icon: str = ""
    decay_per_tick: float = 0.005
    effects: dict[str, float] = {}   # speed_multiplier, damage_multiplier, sociability_bonus
    triggers: dict[str, float] = {}  # event_type → intensity_delta

# DefinitionContainer — new field
emotions: dict[str, EmotionDef] = Field(default_factory=dict)

# Agent — new field
emotions: dict[str, dict] = field(default_factory=dict)
# {"happy": {"intensity": 0.7, "last_trigger_tick": 1234}}

# EmotionManager public API
class EmotionManager:
    @staticmethod
    def apply_trigger(agent, event_type, tick) -> None
    @staticmethod
    def process_tick(agent, tick) -> list[str]  # returns expired
    @staticmethod
    def get_total_modifiers(agent) -> dict[str, float]
    @staticmethod
    def get_dominant_emotion(agent) -> tuple[str, float] | None
    @staticmethod
    def get_emotional_state_str(agent) -> str
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `apply_trigger` — intensity increase, 1.0 cap, cooldown prevention | Direct calls, assert dict values |
| Unit | `process_tick` — decay per tick, removal at ≤0, multiple emotions | Process N ticks, verify removal |
| Unit | `get_total_modifiers` — single/multiple emotions, strongest-wins, empty | Compare returned dict with expected |
| Unit | `get_dominant_emotion` — highest intensity, ties, no emotions | Edge cases |
| Unit | `get_emotional_state_str` — format string for LLM | Format check |
| Unit | Agent default emotions is `{}` | Assert on new Agent() |
| Unit | Unknown trigger is no-op | Assert no KeyError |
| Regression | Existing tests pass unchanged | `pytest tests/ -v` |

## Migration / Rollout

No migration required. New field defaults to `{}` on existing agents — zero-impact add.

## Open Questions

None.
