# Tasks: Weather & Time System

**New files**: time.py, weather.py, weather.yaml, test_time.py, test_weather.py
**Modified files**: definition_models.py, definitions.py, simulation.yaml, status_effects.yaml, emotions.yaml, structures.yaml, skills.yaml, world.py, engine.py, agent.py, snapshot.py, schemas.py, prompts.py

## Phase 1 — Infrastructure (7 tasks)

- [x] **1.1**: Add `WeatherDef` model + `TimeConfig` to `definition_models.py`; add `weather: dict[str, WeatherDef]` to `DefinitionContainer`, `time_config: TimeConfig` to `DefinitionContainer`, `shelter_protection: float` to `StructureDef`.
- [x] **1.2**: Add `weather.yaml` to `_YAML_FILES` in `definitions.py`.
- [x] **1.3**: Create `configs/definitions/weather.yaml` with 5 weather types (clear, rainy, storm, fog, heatwave) — transitions, durations, effects, status_effects_to_apply, emotion_triggers.
- [x] **1.4**: Add `time` section to `simulation.yaml` (`day_length_ticks: 1000`, `daylight_ticks: 600`, `effects.night` multipliers).
- [x] **1.5**: Add `Wet`, `Chilled`, `Overheated` status effects to `status_effects.yaml`.
- [x] **1.6**: Add `on_weather_clear/rain/storm/fog/heatwave` trigger events to `emotions.yaml`.
- [x] **1.7**: Add `shelter_protection` to structures (house: 1.0, storage_hut: 0.5); add `weather_resistance: 0.01` to survival skill in `skills.yaml`.

## Phase 2 — Core Modules (3 tasks)

- [x] **2.1**: Create `backend/app/simulation/time.py` with `TimeSystem` — tick(), is_night, time_of_day_label, get_night_multiplier().
- [x] **2.2**: Create `backend/app/simulation/weather.py` with `WeatherSystem` — tick(), get_effects_for_agent(), _transition(), shelter protection math.
- [x] **2.3**: Add `time` + `weather` fields to `World`; add `advance_time(agents,tick)` calling both subsystems.

## Phase 3 — Engine Integration (5 tasks)

- [x] **3.1**: Call `world.advance_time(self.agents, tick=tick)` in engine `_tick()` after `_process_needs()`.
- [x] **3.2**: Add shelter-seeking priority in `_fsm_evaluate()` — if extreme weather + exposed + shelter nearby, set seeking_shelter and move.
- [x] **3.3**: Apply weather effects via StatusEffectManager.apply() + EmotionManager.apply_trigger() with shelter protection falloff (integrated into WeatherSystem.tick).
- [x] **3.4**: Add night multipliers to `_process_needs()` (thirst decay, energy regen).
- [x] **3.5**: Composite weather modifiers into `get_action_duration()` (multiplicative with skill/status/emotion mods).

## Phase 4 — LLM + Snapshot (2 tasks)

- [x] **4.1**: Add `time_state` + `weather_state` to `WorldSnapshot` schema and snapshot builder.
- [x] **4.2**: Inject `Weather: {weather}` + `Time: {time}` into LLM `STATE_PROMPT_TEMPLATE`.

## Phase 5 — Tests (2 tasks)

- [x] **5.1**: Create `tests/test_time.py` — tick progression, day boundary, is_night, night multiplier (11 tests).
- [x] **5.2**: Create `tests/test_weather.py` — transitions (mocked random), duration countdown, status effects per type, shelter protection calc (22 tests).

## Phase 6 — Validation (2 tasks)

- [x] **6.1**: Run `python -m pytest tests/ -v`, confirm zero regression (478 passed, 0 failed).
- [x] **6.2**: Verify app starts without errors — DEFINITIONS, TimeSystem, WeatherSystem, World all load correctly.
