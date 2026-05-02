# Design: Weather & Time System

## Technical Approach

Two new classes — `TimeSystem` and `WeatherSystem` — live on the `World` object and are driven by the engine tick loop. Weather effects piggyback on existing `StatusEffectManager` (applies Wet/Chilled/Overheated) and `EmotionManager` (storm→fearful, rain→sad, clear→happy). Shelter protection uses exponential falloff: `effective_mult = 1.0 - (protection²)`. All weather data is YAML-driven via a new `weather.yaml` loaded by the existing DEFINITIONS singleton. No new FSM states — shelter-seeking is a priority check in `_fsm_evaluate`.

## Architecture Decisions

| Decision | Option | Rationale |
|----------|--------|-----------|
| Where TimeSystem/WeatherSystem live | `World.time` + `World.weather` | World is the natural state holder; engine calls `world.advance_time(agents)` each tick |
| File split | `time.py` + `weather.py` (separate) | Single responsibility; `weather.py` is complex enough to justify its own file |
| Weather data model | YAML → new `WeatherDef` Pydantic model | Follows exact same pattern as `StatusEffectDef`, `EmotionDef`; loaded by existing DEFINITIONS loader |
| Shelter protection | Exponential falloff: `1.0 - (protection²)` | Proposal specs: full protection at 1.0, 75% at 0.5, 0% at 0.0 |
| Status effect application | Via existing `StatusEffectManager.apply()` | Zero new code paths; weather just triggers effects the same way poisoned berries do |
| Emotion triggers | Via existing `EmotionManager.apply_trigger()` | Uses `on_weather_{type}` event keys added to emotion YAML |
| Modifier aggregation | Composited into `get_action_duration()` | Existing `get_action_duration` already composites skill + status + emotion modifiers — add weather modifiers to same chain |
| DSeparate weather file in DEFINITIONS | `configs/definitions/weather.yaml` | Keeps weather data isolated; add entry in `_YAML_FILES` in `definitions.py` |

### Rejected Alternatives

| Alternative | Rejected because |
|-------------|-----------------|
| Custom weather effect manager | Duplicates StatusEffectManager's strongest-wins aggregation and tick logic — unnecessary |
| New FSM states for shelter-seeking | Same effect achieved via priority check in existing `_fsm_evaluate`; new states add complexity and risk |
| TimeSystem as standalone module | World is the natural owner — TimeSystem has no life outside a World instance |
| JSON for weather definitions | YAML is the project convention for ALL definition files; consistency > format preference |

## Data Flow

```
Tick N
  │
  ├─ _process_needs()
  │
  ├─ StatusEffectManager.process_tick(agent)   ← weather effects tick here
  ├─ EmotionManager.process_tick(agent, tick)  ← weather emotions tick here
  │
  ├─ world.advance_time(agents)     ← NEW: TimeSystem.tick() + WeatherSystem.tick()
  │    │
  │    ├─ TimeSystem.tick()
  │    │   └─ tick_count_of_day++ → day transition if needed
  │    │
  │    └─ WeatherSystem.tick(agents, world)
  │        ├─ remaining_ticks-- → transition if expired
  │        ├─ StatusEffectManager.apply(agent, "wet") for exposed agents
  │        ├─ EmotionManager.apply_trigger(agent, "on_weather_storm") etc.
  │        └─ Returns weather_changes dict
  │
  ├─ storage proximity check
  │
  ├─ _run_agent_fsm()
  │    └─ _fsm_evaluate()
  │         ├─ feed child check (existing)
  │         ├─ shelter-seeking check  ← NEW: if weather is extreme
  │         ├─ role priorities (existing)
  │         └─ survival chain (existing)
  │
  ├─ ... (rest of tick unchanged)
  │
  └─ snapshot builder
       └─ includes time_state + weather_state ← NEW fields
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/simulation/time.py` | Create | `TimeSystem` class: day/night cycle, `is_night`, `time_of_day_label` |
| `backend/app/simulation/weather.py` | Create | `WeatherSystem` class: state machine, transitions, effect application |
| `backend/app/simulation/world.py` | Modify | Add `self.time = TimeSystem()` + `self.weather = WeatherSystem()` and `advance_time(agents)` method |
| `backend/app/simulation/engine.py` | Modify | Insert `world.advance_time()` after needs/effects processing; add shelter-seeking in `_fsm_evaluate`; composite weather modifiers in `get_action_duration` |
| `backend/app/simulation/agent.py` | Modify | Add `seeking_shelter` field to FSM evaluate flow |
| `backend/app/simulation/snapshot.py` | Modify | Include `time_state` + `weather_state` in snapshot |
| `backend/app/models/schemas.py` | Modify | Add `time_state: dict` and `weather_state: dict` to `WorldSnapshot` |
| `backend/app/ai/prompts.py` | Modify | Inject `Weather: {type}` + `Time: {phase} (tick {n}/{max})` into `STATE_PROMPT_TEMPLATE` |
| `backend/app/core/definition_models.py` | Modify | Add `WeatherDef` model, add `time: TimeConfig` to `SimulationConfig`, add `shelter_protection: float` to `StructureDef` |
| `backend/app/core/definitions.py` | Modify | Add `weather.yaml` to `_YAML_FILES` loading list |
| `configs/definitions/weather.yaml` | Create | 5 weather types: clear, rainy, storm, fog, heatwave with transitions, durations, effects, status_effects_to_apply |
| `configs/definitions/status_effects.yaml` | Modify | Add wet, chilled, overheated effects |
| `configs/definitions/emotions.yaml` | Modify | Add weather trigger events: `on_weather_clear`, `on_weather_rain`, `on_weather_storm`, `on_weather_fog`, `on_weather_heatwave` |
| `configs/definitions/structures.yaml` | Modify | Add `shelter_protection` to house (1.0), storage_hut (0.5), others (0.0) |
| `configs/definitions/skills.yaml` | Modify | Add `weather_resistance: 0.01` to survival skill `effects_per_level` |
| `configs/definitions/simulation.yaml` | Modify | Add `time` section with `day_length_ticks`, `daylight_ticks`, `effects.night` |
| `backend/tests/test_time.py` | Create | Unit tests for TimeSystem |
| `backend/tests/test_weather.py` | Create | Unit tests for WeatherSystem |

## Interfaces / Contracts

### TimeSystem (`app/simulation/time.py`)

```python
class TimeSystem:
    def __init__(self, day_length_ticks: int = 1000, daylight_ticks: int = 600): ...
    def tick(self) -> None: ...
    @property
    def is_night(self) -> bool: ...
    @property
    def time_of_day_label(self) -> str: ...
    def get_night_multiplier(self, stat_name: str) -> float: ...
```

### WeatherSystem (`app/simulation/weather.py`)

```python
class WeatherSystem:
    def __init__(self, initial_weather: str = "clear"): ...
    def tick(self, agents: list[Agent], world: World) -> dict: ...
    def get_effects_for_agent(self, agent: Agent, structures_at_position: list) -> dict: ...
    def _transition(self) -> None: ...
```

### WeatherDef (`app/core/definition_models.py`)

```python
class WeatherDef(BaseModel):
    name: str
    icon: str
    category: str  # fair, precipitation, fog, extreme
    duration_min: int
    duration_max: int
    visibility_multiplier: float = 1.0
    resource_regen_multiplier: float = 1.0
    effects: dict[str, float] = {}  # stat modifiers
    status_effects_to_apply: list[str] = []
    emotion_triggers: dict[str, float] = {}
    transitions: dict[str, int] = {}  # next_weather → weight
```

### Modified World contract

```python
class World:
    time: TimeSystem = field(init=False)
    weather: WeatherSystem = field(init=False)

    def advance_time(self, agents: list[Agent]) -> dict:
        """Tick time + weather, apply weather effects to agents."""
```

### Snapshot additions (`app/models/schemas.py`)

```python
class WorldSnapshot(BaseModel):
    # ... existing fields ...
    time_state: dict = {}   # {"is_night": bool, "tick_count_of_day": int, "day_count": int}
    weather_state: dict = {}  # {"current_weather": str, "remaining_ticks": int}
```

### StructureDef addition

```python
class StructureDef(BaseModel):
    # ... existing fields ...
    shelter_protection: float = 0.0  # 0.0 (none) to 1.0 (full)
```

## Weather Modifier Composition in `get_action_duration`

Weather modifiers compose multiplicatively with existing skill + status + emotion modifiers:

```python
# In get_action_duration (actions.py)
effect_mod = StatusEffectManager.get_total_modifiers(agent).get("speed_multiplier", 1.0)
emotion_mod = EmotionManager.get_total_modifiers(agent).get("speed_multiplier", 1.0)
weather_mod = 1.0  # ← NEW: computed from weather effects with shelter protection
return max(1, round(base * skill_mod * effect_mod * emotion_mod * weather_mod))
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit — TimeSystem | Tick progression, day boundary, day count increment, is_night, night multiplier | Direct instantiation like test_status_effects.py (class `TestTimeSystem`, simple assertions, no mocks) |
| Unit — WeatherSystem | Transition weighted random, duration countdown, effects dict, status effect application per weather type, shelter protection calc | `TestWeatherSystem` class; mock `random` for deterministic transitions; assert `status_effects_to_apply` passed to StatusEffectManager |
| Unit — World advance_time | State propagation: time.tick called, weather.tick called, agents receive effects | Create World, call advance_time with mock agents, assert world.time + world.weather advanced |
| Integration — Engine | Weather modifies action duration in `get_action_duration` | Call `get_action_duration()` with weather effect active on agent |
| Snapshot | time_state and weather_state in snapshot | Build snapshot, verify new fields present |
| Regression | All 422+ existing tests pass | Run `python -m pytest tests/ -v` after changes |

## Migration / Rollout

No migration required. All new data is YAML-defined and loaded at import time. Existing `DefinitionContainer` gains new `weather` key — existing YAML files untouched except for additions to `status_effects.yaml`, `emotions.yaml`, `structures.yaml`, `simulation.yaml`, `skills.yaml`. The DEFINITIONS loader handles new files deterministically via `_YAML_FILES`.

## Open Questions

- [ ] Should `weather.yaml` transitions be normalized (weights sum to 100) or raw? Design assumes raw weights with `random.choices()` normalization.
- [ ] Night multipliers: which agent stats should night affect? Design proposes `resource_regen_multiplier`, `thirst_decay_multiplier`, `energy_regen_multiplier`, `visibility_multiplier` — confirm with team.
- [ ] `shelter_protection` for `forge` — should a forge provide any protection? Design defaults to 0.0 for forge/wall/farm/workbench.
