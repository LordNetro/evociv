# Delta for weather-time-system

## ADDED Requirements

| # | Requirement | Strength |
|---|-------------|----------|
| T1 | System MUST load time config from `simulation.yaml[time]`: `day_length_ticks`, `daylight_ticks`, `night_ticks` (all integers). Sum of `daylight_ticks + night_ticks` SHOULD equal `day_length_ticks`. | MUST |
| T2 | System MUST track `tick_count_of_day` (0 to `day_length_ticks`-1). Each tick increments by 1. On rollover at `day_length_ticks`, reset to 0 and increment `day_count`. `is_night` = True when `tick_count_of_day >= daylight_ticks`. | MUST |
| T3 | During night: resource regeneration × `night.resource_regen_multiplier` (default 0.5). Thirst decay × `night.thirst_decay_multiplier` (default 0.5). Energy recovery during rest × `night.energy_regen_multiplier` (default 1.5). All configurable in `simulation.yaml[night]`. | MUST |
| W1 | System MUST load weather definitions from `weather.yaml`. Each type MUST include: `name`, `icon`, `category` (fair/precipitation/extreme/fog), `duration_min`/`max`, `visibility_multiplier`, `resource_regen_multiplier`, `effects` (attr→multiplier), `status_effects_to_apply` (list), `emotion_triggers` (event→delta), `transitions` (next_weather→weight). | MUST |
| W2 | System MUST maintain `current_weather` and `remaining_ticks`. Each tick decrements `remaining_ticks`. At 0, weighted random selects next weather from current weather's `transitions`. Weight-0 entries MUST NOT be selectable. | MUST |
| W3 | On weather change, system MUST apply configured status effects to all exposed agents. Weather modifiers aggregate via `StatusEffectManager.get_total_modifiers()` and compose multiplicatively with existing modifiers. Visibility modifiers tracked separately per agent. | MUST |
| W4 | On weather change, system MUST call `EmotionManager.apply_trigger(agent, weather.emotion_trigger_event, tick)` for all exposed agents. | MUST |
| S1 | Each structure definition MUST include `shelter_protection` (float 0.0–1.0). Agent on a structure tile: `effective_mult = 1.0 - (shelter_protection²)`. Full protection (1.0) MUST eliminate ALL weather effects. | MUST |
| S2 | FSM `evaluate` MUST check: if weather is extreme AND agent exposed (`effective_mult > 0.5`) AND shelter within interaction radius → prioritize MOVE to shelter over other actions. | MUST |
| L1 | LLM prompt MUST include `Weather: {name} ({icon})` and `Time: {Day/Night} (Day {day_count}, tick {count}/{total})`. | MUST |

### Scenarios

#### T2 — Tick rollover
- GIVEN `tick_count_of_day=9`, `day_length_ticks=10`, `day_count=5`
- WHEN 1 simulation tick passes
- THEN `tick_count_of_day=0` AND `day_count=6`

#### T2 — Night detection
- GIVEN `tick_count_of_day=7`, `daylight_ticks=7`
- WHEN `is_night` is queried
- THEN `is_night=True`

#### T3 — Night resource regen penalty
- GIVEN `is_night=True`, `night.resource_regen_multiplier=0.5`
- WHEN resource regeneration is calculated
- THEN effective regen = base_regen × 0.5

#### T3 — Night energy recovery bonus
- GIVEN `is_night=True`, `night.energy_regen_multiplier=1.5`
- WHEN an agent rests during night
- THEN energy gain = base_regen × 1.5

#### W2 — Weighted random transition
- GIVEN Rain at `remaining_ticks=1`
- WHEN 1 tick passes
- THEN `remaining_ticks=0` AND next weather selected via weighted random from `Rain.transitions`

#### W2 — Zero-weight exclusion
- GIVEN `Rain.transitions={Storm: 0, Clear: 10}`
- WHEN Rain expires
- THEN Storm MUST NOT be selected as next weather

#### W3 — Status effects applied on weather change
- GIVEN weather changes to Rain with `status_effects_to_apply=["wet"]`
- WHEN change is processed
- THEN `StatusEffectManager.apply(agent, "wet")` is called for all exposed agents

#### W4 — Emotion triggers on weather change
- GIVEN weather changes to Clear with `emotion_triggers={"sky_clear": +0.2}`
- WHEN change is processed
- THEN `EmotionManager.apply_trigger(agent, "sky_clear", tick)` is called for all exposed agents

#### S1 — Full shelter immunity
- GIVEN house with `shelter_protection=1.0`
- THEN `effective_mult = 0.0` (all weather effects eliminated)

#### S1 — Partial shelter reduction
- GIVEN storage_hut with `shelter_protection=0.5`
- THEN `effective_mult = 0.75` (weather effects reduced by 25%)

#### S2 — Shelter-seeking prioritization
- GIVEN Storm active, agent on open ground (`effective_mult=1.0`), shelter within 3 tiles
- WHEN FSM `evaluate` runs
- THEN agent's selected action is MOVE toward shelter

#### L1 — Daytime LLM prompt
- GIVEN `weather=Rain(🌧)`, `tick=500/1000`, `day=3`, `is_night=False`
- WHEN LLM prompt is built
- THEN prompt includes `Weather: Rain (🌧)` AND `Time: Day (Day 3, tick 500/1000)`

#### L1 — Nighttime LLM prompt
- GIVEN `tick=800/1000`, `daylight_ticks=700`, `is_night=True`
- WHEN LLM prompt is built
- THEN prompt includes `Time: Night` in the time status
