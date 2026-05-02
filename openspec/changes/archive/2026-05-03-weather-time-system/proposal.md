# Proposal: Weather & Time System

## Intent

Add day/night cycle and weather to the simulation. Weather affects resource regen, agent attributes, status effects, emotions, and visibility. Shelters mitigate exposure. LLM gets time/weather context for more grounded decisions.

## Scope

### In Scope
- TimeSystem: day/night cycle (1000 ticks/day, configurable), dawn/dusk transitions, `is_night` flag
- WeatherSystem: 5 types (Clear, Rain, Storm, Fog, Heatwave), weighted-random transitions on expiry
- YAML definitions: `weather.yaml` (new), additions to `simulation.yaml`, `structures.yaml`, `skills.yaml`
- Status effects: Wet, Chilled, Overheated (in existing `status_effects.yaml`)
- Shelter protection on structures (house=1.0, storage_hut=0.5, others=0.0)
- Shelter-seeking in FSM evaluate state
- Weather modifiers on action duration
- Weather/time in LLM prompts, snapshots, schemas
- Full test coverage (unit + integration, zero regression)

### Out of Scope
- Visual weather effects (rain particles, sky color) — graphical phase
- Seasons — V2
- Temperature tracking — V2
- Weather forecasting for LLM — deferred

## Capabilities

### New Capabilities
- `weather-time-system`: Day/night tick tracking + weather state machine with YAML-driven definitions, transitions, and effects

### Modified Capabilities
- `status-effect-system`: Weather applies Wet, Chilled, Overheated via existing StatusEffectManager
- `emotion-system`: Weather events trigger emotions (sun→happy, rain→sad, storm→fearful)
- `skill-system`: Survival skill gains `weather_resistance` attribute to mitigate weather effects
- `structures`: Each structure gains `shelter_protection` (0.0–1.0) for weather mitigation
- `architecture`: Tick loop integrates weather/time processing alongside status effects and emotions

## Approach

Reuse existing systems over building new ones. Weather effects → StatusEffectManager. Weather emotions → EmotionManager. Shelter → exponential falloff: `effective_mult = 1.0 - (shelter_protection²)`. No new FSM states — shelter-seeking is a priority check in the existing evaluate flow. All weather data lives in `weather.yaml` loaded by the DEFINITIONS singleton.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/simulation/weather_system.py` | New | TimeSystem + WeatherSystem classes |
| `app/simulation/engine.py` | Modified | Tick loop calls weather/time processing |
| `app/simulation/world.py` | Modified | World holds time_state + weather_state |
| `app/simulation/agent.py` | Modified | Agent gains shelter check in FSM |
| `app/ai/prompts.py` | Modified | Weather/time injected into LLM prompt |
| `app/models/schemas.py` | Modified | Snapshot includes time + weather data |
| `configs/definitions/weather.yaml` | New | 5 weather types with durations, weights, effects |
| `configs/definitions/status_effects.yaml` | Modified | Add Wet, Chilled, Overheated |
| `configs/definitions/structures.yaml` | Modified | Add shelter_protection to structures |
| `configs/definitions/skills.yaml` | Modified | Add weather_resistance to survival skill |
| `configs/simulation.yaml` | Modified | Add day_length_ticks, weather config |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Weather processing slows tick loop | Low | O(n agents) — same as status effects; profile before optimizing |
| Shelter-seeking FSM change breaks existing behavior | Low | Shielded behind `shelter_protection > 0` check; existing agents have no shelter |
| Weather status effects conflict with existing ones | Low | Reuses strongest-wins aggregation; Wet/Chilled/Overheated are new unique names |

## Rollback Plan

1. Revert all changes (git revert: `openspec/changes/weather-time-system/` and all modified files)
2. Remove `weather.yaml` from DEFINITIONS loader to prevent KeyError
3. Revert `simulation.yaml` to remove day_length_ticks
4. Run full test suite to confirm zero regression

## Dependencies

- DEFINITIONS singleton & YAML loader (existing)
- StatusEffectManager, EmotionManager (existing)
- StructureManager (existing) — for shelter_proximity checks

## Success Criteria

- [ ] All 422 existing tests pass (zero regression)
- [ ] New weather/time unit tests pass
- [ ] Weather transitions at correct intervals with correct weights
- [ ] Status effects applied: Wet from Rain, Chilled from Storm
- [ ] Emotions triggered: sad from Rain, fearful from Storm, happy from Clear
- [ ] Shelter protection reduces weather effects (house=full, none=exposed)
- [ ] LLM prompt includes `Weather: {type}` + `Time: {phase} (tick {n}/{max})`
- [ ] Snapshot includes `time_state` + `weather_state` fields
