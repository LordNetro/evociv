"""Tests for the status effect system."""

from app.simulation.agent import Agent
from app.simulation.status_effects import StatusEffectManager


class TestStatusEffectManager:
    """TDD Cycle for StatusEffectManager."""

    def test_apply_new_effect(self):
        """RED: Apply a new effect to an agent with no active effects."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        assert agent.active_effects == {}

        result = StatusEffectManager.apply(agent, "poisoned")

        assert result is True
        assert "poisoned" in agent.active_effects
        assert agent.active_effects["poisoned"]["remaining_ticks"] == 60
        assert agent.active_effects["poisoned"]["current_stacks"] == 1

    def test_apply_refresh_additive_duration(self):
        """RED: Re-applying an effect adds duration (capped)."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        StatusEffectManager.apply(agent, "poisoned")
        assert agent.active_effects["poisoned"]["remaining_ticks"] == 60

        StatusEffectManager.apply(agent, "poisoned")
        # 60 + 60 = 120, but max_stacks=3 so max = 60 * 3 = 180
        assert agent.active_effects["poisoned"]["remaining_ticks"] == 120
        assert agent.active_effects["poisoned"]["current_stacks"] == 2

    def test_apply_stacks_capped(self):
        """RED: Stacks are capped at max_stacks."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        for _ in range(5):
            StatusEffectManager.apply(agent, "poisoned")
        assert agent.active_effects["poisoned"]["current_stacks"] == 3  # max_stacks
        # Duration cap: 60 * 3 = 180
        assert agent.active_effects["poisoned"]["remaining_ticks"] == 180

    def test_process_tick_decrements_all(self):
        """RED: process_tick decrements remaining_ticks by 1."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        StatusEffectManager.apply(agent, "poisoned")
        assert agent.active_effects["poisoned"]["remaining_ticks"] == 60

        expired = StatusEffectManager.process_tick(agent)
        assert agent.active_effects["poisoned"]["remaining_ticks"] == 59
        assert expired == []

    def test_process_tick_expires_effect(self):
        """RED: Effect with 1 remaining tick expires on next tick."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        StatusEffectManager.apply(agent, "poisoned")
        agent.active_effects["poisoned"]["remaining_ticks"] = 1

        expired = StatusEffectManager.process_tick(agent)

        assert "poisoned" not in agent.active_effects
        assert "poisoned" in expired

    def test_has_effect(self):
        """RED: has_effect returns True/False correctly."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        assert StatusEffectManager.has_effect(agent, "poisoned") is False
        StatusEffectManager.apply(agent, "poisoned")
        assert StatusEffectManager.has_effect(agent, "poisoned") is True

    def test_remove_effect(self):
        """RED: remove_effect removes a specific effect."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        StatusEffectManager.apply(agent, "poisoned")
        StatusEffectManager.apply(agent, "exhausted")

        removed = StatusEffectManager.remove_effect(agent, "poisoned")
        assert removed is True
        assert "poisoned" not in agent.active_effects
        assert "exhausted" in agent.active_effects

    def test_remove_nonexistent_effect(self):
        """RED: Removing nonexistent effect returns False."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        removed = StatusEffectManager.remove_effect(agent, "poisoned")
        assert removed is False

    def test_clear_all(self):
        """RED: clear_all removes all active effects."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        StatusEffectManager.apply(agent, "poisoned")
        StatusEffectManager.apply(agent, "exhausted")
        StatusEffectManager.apply(agent, "well_fed")

        StatusEffectManager.clear_all(agent)
        assert agent.active_effects == {}

    def test_get_total_modifiers_empty(self):
        """RED: No effects returns empty modifiers dict."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        mods = StatusEffectManager.get_total_modifiers(agent)
        assert mods == {}

    def test_get_total_modifiers_single_effect(self):
        """RED: Single effect returns its modifiers."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        StatusEffectManager.apply(agent, "poisoned")
        mods = StatusEffectManager.get_total_modifiers(agent)
        assert "health_delta" in mods
        assert mods["health_delta"] == -0.5

    def test_get_total_modifiers_strongest_wins(self):
        """RED: Same attribute from multiple effects uses strongest-wins."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        # Apply poisoned (health_delta: -0.5) + bleeding (health_delta: -0.8)
        StatusEffectManager.apply(agent, "poisoned")
        StatusEffectManager.apply(agent, "bleeding")
        mods = StatusEffectManager.get_total_modifiers(agent)
        # Strongest (most negative) wins: -0.8
        assert mods["health_delta"] == -0.8

    def test_get_total_modifiers_multiple_attrs(self):
        """RED: Multiple attributes are all included."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        StatusEffectManager.apply(agent, "well_fed")
        mods = StatusEffectManager.get_total_modifiers(agent)
        assert "speed_multiplier" in mods
        assert "health_regen" in mods

    def test_apply_unknown_effect(self):
        """RED: Unknown effect name returns False and does nothing."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        result = StatusEffectManager.apply(agent, "nonexistent_effect")
        assert result is False
        assert agent.active_effects == {}
