"""Tests for the WeatherSystem — weather state machine, transitions, effects.

Written FIRST (TDD RED phase), WeatherSystem does not yet exist.
"""

import random
from unittest.mock import patch

from app.simulation.weather import WeatherSystem
from app.simulation.agent import Agent


class TestWeatherSystem:
    """TDD Cycle for WeatherSystem."""

    def test_initial_state(self):
        """RED: WeatherSystem starts with 'clear' weather by default."""
        ws = WeatherSystem()
        assert ws.current_weather == "clear"
        assert ws.remaining_ticks > 0

    def test_initial_state_custom(self):
        """RED: WeatherSystem accepts initial_weather parameter."""
        ws = WeatherSystem(initial_weather="rainy")
        assert ws.current_weather == "rainy"

    def test_tick_decrements_remaining(self):
        """RED: tick() decrements remaining_ticks by 1."""
        ws = WeatherSystem()
        initial = ws.remaining_ticks
        ws.tick(agents=[], world=None)
        assert ws.remaining_ticks == initial - 1

    def test_tick_no_transition_when_remaining(self):
        """RED: When remaining_ticks > 0, weather does not change."""
        ws = WeatherSystem()
        ws.remaining_ticks = 50
        ws.tick(agents=[], world=None)
        assert ws.current_weather == "clear"

    def test_transition_on_depletion(self):
        """RED: When remaining_ticks hits 0, weather transitions to a new type."""
        ws = WeatherSystem()
        ws.remaining_ticks = 0
        with patch("random.choices") as mock_choices:
            mock_choices.return_value = ["rainy"]
            ws.tick(agents=[], world=None)
            assert ws.current_weather == "rainy"
            assert ws.remaining_ticks > 0

    def test_duration_within_bounds(self):
        """RED: After transition, remaining_ticks is between duration_min and duration_max."""
        ws = WeatherSystem()
        ws.remaining_ticks = 0
        with patch("random.choices") as mock_choices:
            mock_choices.return_value = ["rainy"]
            ws.tick(agents=[], world=None)
            weather_def = ws._get_current_def()
            assert weather_def.duration_min <= ws.remaining_ticks <= weather_def.duration_max

    def test_get_current_def_returns_valid(self):
        """RED: _get_current_def returns the WeatherDef for current_weather."""
        ws = WeatherSystem()
        wd = ws._get_current_def()
        assert wd is not None
        assert wd.name == "clear"

    def test_get_current_def_nonexistent(self):
        """RED: _get_current_def returns None for unknown weather."""
        ws = WeatherSystem()
        ws.current_weather = "nonexistent"
        assert ws._get_current_def() is None


class TestWeatherSystemShelterProtection:
    """Tests for shelter protection math: 1.0 - (protection²)."""

    def test_shelter_protection_full(self):
        """RED: protection=1.0 gives effective_mult=0.0 (fully protected)."""
        ws = WeatherSystem()
        result = ws._shelter_multiplier(1.0)
        assert result == 0.0

    def test_shelter_protection_half(self):
        """RED: protection=0.5 gives effective_mult=0.75 (75% exposure)."""
        ws = WeatherSystem()
        result = ws._shelter_multiplier(0.5)
        assert result == 0.75

    def test_shelter_protection_none(self):
        """RED: protection=0.0 gives effective_mult=1.0 (fully exposed)."""
        ws = WeatherSystem()
        result = ws._shelter_multiplier(0.0)
        assert result == 1.0

    def test_shelter_protection_partial_02(self):
        """RED: protection=0.2 gives effective_mult=0.96."""
        ws = WeatherSystem()
        result = ws._shelter_multiplier(0.2)
        assert result == 0.96


class TestWeatherSystemEffects:
    """Tests for weather effect aggregation."""

    def test_get_effects_for_agent_no_shelter(self):
        """RED: Agent with no shelter gets full weather effects."""
        ws = WeatherSystem(initial_weather="rainy")
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        effects = ws.get_effects_for_agent(agent, shelter_mult=1.0)
        assert "speed_multiplier" in effects
        assert effects["speed_multiplier"] < 1.0

    def test_get_effects_for_agent_full_shelter(self):
        """RED: Agent with full shelter gets no weather effects (mult=0)."""
        ws = WeatherSystem(initial_weather="rainy")
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        effects = ws.get_effects_for_agent(agent, shelter_mult=0.0)
        assert effects == {}

    def test_get_effects_for_agent_partial_shelter(self):
        """RED: Agent with partial shelter gets reduced effects."""
        ws = WeatherSystem(initial_weather="rainy")
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        full = ws.get_effects_for_agent(agent, shelter_mult=1.0)
        partial = ws.get_effects_for_agent(agent, shelter_mult=0.5)
        # All values in partial should be <= corresponding values in full
        for key in full:
            if key != "speed_multiplier":
                continue
            # For speed_multiplier (which is < 1.0), partial should be closer to 1.0
            if full[key] < 1.0:
                assert partial.get(key, 1.0) >= full[key]
            elif full[key] > 1.0:
                assert partial.get(key, 1.0) <= full[key]


class TestWeatherSystemStatusEffects:
    """Tests for status effects applied by weather."""

    def test_clear_weather_no_status_effects(self):
        """RED: Clear weather applies no status effects."""
        ws = WeatherSystem(initial_weather="clear")
        assert ws.get_status_effects_to_apply() == []

    def test_rainy_weather_applies_wet(self):
        """RED: Rainy weather applies 'wet' status effect."""
        ws = WeatherSystem(initial_weather="rainy")
        effects = ws.get_status_effects_to_apply()
        assert "wet" in effects

    def test_storm_weather_applies_wet_chilled(self):
        """RED: Storm weather applies 'wet' and 'chilled' status effects."""
        ws = WeatherSystem(initial_weather="storm")
        effects = ws.get_status_effects_to_apply()
        assert "wet" in effects
        assert "chilled" in effects

    def test_fog_weather_applies_chilled(self):
        """RED: Fog weather applies 'chilled' status effect."""
        ws = WeatherSystem(initial_weather="fog")
        effects = ws.get_status_effects_to_apply()
        assert "chilled" in effects

    def test_heatwave_applies_overheated(self):
        """RED: Heatwave weather applies 'overheated' status effect."""
        ws = WeatherSystem(initial_weather="heatwave")
        effects = ws.get_status_effects_to_apply()
        assert "overheated" in effects


class TestWeatherSystemEmotionTriggers:
    """Tests for weather-based emotion triggers."""

    def test_clear_triggers_happy(self):
        """RED: Clear weather triggers 'on_weather_clear'."""
        ws = WeatherSystem(initial_weather="clear")
        triggers = ws.get_emotion_triggers()
        assert "on_weather_clear" in triggers

    def test_rain_triggers_sad(self):
        """RED: Rainy weather triggers 'on_weather_rain'."""
        ws = WeatherSystem(initial_weather="rainy")
        triggers = ws.get_emotion_triggers()
        assert "on_weather_rain" in triggers

    def test_storm_triggers_fearful(self):
        """RED: Storm weather triggers 'on_weather_storm'."""
        ws = WeatherSystem(initial_weather="storm")
        triggers = ws.get_emotion_triggers()
        assert "on_weather_storm" in triggers

    def test_fog_triggers_fearful(self):
        """RED: Fog weather triggers 'on_weather_fog'."""
        ws = WeatherSystem(initial_weather="fog")
        triggers = ws.get_emotion_triggers()
        assert "on_weather_fog" in triggers

    def test_heatwave_triggers_angry(self):
        """RED: Heatwave weather triggers 'on_weather_heatwave'."""
        ws = WeatherSystem(initial_weather="heatwave")
        triggers = ws.get_emotion_triggers()
        assert "on_weather_heatwave" in triggers


class TestWeatherSystemWeatherState:
    """Tests for weather_state snapshot data."""

    def test_get_weather_state(self):
        """RED: get_weather_state returns current weather info dict."""
        ws = WeatherSystem(initial_weather="clear")
        state = ws.get_weather_state()
        assert state["current_weather"] == "clear"
        assert "remaining_ticks" in state
        assert "category" in state

    def test_get_weather_state_after_transition(self):
        """RED: get_weather_state reflects transitions."""
        ws = WeatherSystem()
        ws.remaining_ticks = 0
        with patch("random.choices") as mock_choices:
            mock_choices.return_value = ["storm"]
            ws.tick(agents=[], world=None)
            state = ws.get_weather_state()
            assert state["current_weather"] == "storm"
