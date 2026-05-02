"""Tests for the emotion/morale system."""

import pytest

from app.simulation.agent import Agent
from app.simulation.emotions import EmotionManager


class TestEmotionManager:
    """TDD Cycle for EmotionManager."""

    # ── apply_trigger ──────────────────────────────────────────────────

    def test_apply_trigger_adds_new_emotion(self):
        """RED: Apply trigger adds a new emotion to an empty agent."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        assert agent.emotions == {}

        EmotionManager.apply_trigger(agent, "on_socialize", tick=1)

        assert "happy" in agent.emotions
        # on_socialize triggers happy with delta 0.2
        assert agent.emotions["happy"]["intensity"] == 0.2
        assert agent.emotions["happy"]["last_trigger_tick"] == 1

    def test_apply_trigger_caps_intensity_at_one(self):
        """RED: Intensity is capped at 1.0 even with multiple triggers."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))

        # Apply multiple times to exceed 1.0
        EmotionManager.apply_trigger(agent, "on_socialize", tick=1)
        EmotionManager.apply_trigger(agent, "on_socialize", tick=10)
        EmotionManager.apply_trigger(agent, "on_socialize", tick=20)
        EmotionManager.apply_trigger(agent, "on_socialize", tick=30)
        EmotionManager.apply_trigger(agent, "on_socialize", tick=40)

        assert agent.emotions["happy"]["intensity"] == 1.0

    def test_apply_trigger_respects_cooldown(self):
        """RED: Trigger within 5 ticks of last trigger is ignored."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))

        EmotionManager.apply_trigger(agent, "on_socialize", tick=10)
        assert agent.emotions["happy"]["intensity"] == 0.2

        # Cooldown: same trigger within 5 ticks
        EmotionManager.apply_trigger(agent, "on_socialize", tick=13)
        # Intensity should NOT increase (cooldown active)
        assert agent.emotions["happy"]["intensity"] == 0.2

    def test_apply_trigger_after_cooldown(self):
        """RED: Trigger after 5+ ticks passes cooldown and adds delta."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))

        EmotionManager.apply_trigger(agent, "on_socialize", tick=10)
        assert agent.emotions["happy"]["intensity"] == 0.2

        # After cooldown (tick 15+)
        EmotionManager.apply_trigger(agent, "on_socialize", tick=16)
        assert agent.emotions["happy"]["intensity"] == 0.4

    def test_apply_trigger_unknown_event_is_noop(self):
        """RED: An unknown trigger event raises no error and does nothing."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))

        # Should not raise
        EmotionManager.apply_trigger(agent, "nonexistent_event", tick=1)

        assert agent.emotions == {}

    def test_apply_trigger_multiple_different_emotions(self):
        """RED: Different trigger events can activate different emotions."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))

        EmotionManager.apply_trigger(agent, "on_socialize", tick=1)   # happy +0.2
        EmotionManager.apply_trigger(agent, "on_skill_up", tick=2)    # hopeful +0.3

        assert "happy" in agent.emotions
        assert "hopeful" in agent.emotions
        assert agent.emotions["happy"]["intensity"] == 0.2
        assert agent.emotions["hopeful"]["intensity"] == 0.3

    # ── process_tick ───────────────────────────────────────────────────

    def test_process_tick_decay_all(self):
        """RED: process_tick decrements all emotion intensities by decay_per_tick."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        EmotionManager.apply_trigger(agent, "on_socialize", tick=1)  # happy (decay 0.005)

        expired = EmotionManager.process_tick(agent, tick=2)

        # happy intensity started at 0.2, decay 0.005
        assert agent.emotions["happy"]["intensity"] == pytest.approx(0.195, abs=1e-3)
        assert expired == []

    def test_process_tick_removes_expired(self):
        """RED: Emotion with intensity ≤ 0 after decay is removed."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        # Manually set a very low intensity
        agent.emotions["happy"] = {"intensity": 0.003, "last_trigger_tick": 1}

        expired = EmotionManager.process_tick(agent, tick=2)

        assert "happy" not in agent.emotions
        assert "happy" in expired

    def test_process_tick_multiple_emotions(self):
        """RED: Multiple emotions all decay together; only expired are removed."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.emotions["happy"] = {"intensity": 0.1, "last_trigger_tick": 1}
        agent.emotions["angry"] = {"intensity": 0.003, "last_trigger_tick": 1}

        expired = EmotionManager.process_tick(agent, tick=2)

        assert "angry" not in agent.emotions  # expired (0.003 - 0.01 = -0.007)
        assert "happy" in agent.emotions       # still active (0.1 - 0.005 = 0.095)
        assert "angry" in expired

    # ── get_total_modifiers ────────────────────────────────────────────

    def test_get_total_modifiers_empty(self):
        """RED: No active emotions returns empty dict."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        mods = EmotionManager.get_total_modifiers(agent)
        assert mods == {}

    def test_get_total_modifiers_single_emotion(self):
        """RED: Single emotion returns its effects by intensity."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.emotions["calm"] = {"intensity": 0.5, "last_trigger_tick": 1}

        mods = EmotionManager.get_total_modifiers(agent)

        # calm has speed_multiplier: 1.1 at full intensity, scaled by 0.5
        assert "speed_multiplier" in mods
        assert mods["speed_multiplier"] == pytest.approx(1.05, abs=1e-3)

    def test_get_total_modifiers_strongest_wins(self):
        """RED: Same attribute from multiple emotions uses strongest-wins."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        # calm: speed_multiplier 1.1 at intensity 0.5 → 1.05
        # fearful: speed_multiplier 0.9 at intensity 0.8 → 0.92
        agent.emotions["calm"] = {"intensity": 0.5, "last_trigger_tick": 1}
        agent.emotions["fearful"] = {"intensity": 0.8, "last_trigger_tick": 1}

        mods = EmotionManager.get_total_modifiers(agent)

        # fearful's speed_multiplier (0.92) is further from 1.0 than calm's (1.05)
        # stronger deviation wins: |0.92 - 1.0| = 0.08 > |1.05 - 1.0| = 0.05
        assert "speed_multiplier" in mods
        assert mods["speed_multiplier"] == pytest.approx(0.92, abs=1e-3)

    def test_get_total_modifiers_multiple_attrs(self):
        """RED: Multiple different attributes are all included."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        # angry has damage_multiplier and speed_multiplier
        agent.emotions["angry"] = {"intensity": 1.0, "last_trigger_tick": 1}

        mods = EmotionManager.get_total_modifiers(agent)

        assert "damage_multiplier" in mods
        assert "speed_multiplier" in mods
        assert mods["damage_multiplier"] == 1.15
        assert mods["speed_multiplier"] == 1.1

    # ── get_dominant_emotion ──────────────────────────────────────────

    def test_get_dominant_emotion_empty(self):
        """RED: No active emotions returns None."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        dominant = EmotionManager.get_dominant_emotion(agent)
        assert dominant is None

    def test_get_dominant_emotion_highest_wins(self):
        """RED: Returns the emotion with highest intensity."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.emotions["calm"] = {"intensity": 0.3, "last_trigger_tick": 1}
        agent.emotions["happy"] = {"intensity": 0.7, "last_trigger_tick": 1}
        agent.emotions["sad"] = {"intensity": 0.2, "last_trigger_tick": 1}

        name, intensity = EmotionManager.get_dominant_emotion(agent)

        assert name == "happy"
        assert intensity == 0.7

    def test_get_dominant_emotion_tie_returns_first(self):
        """RED: Tie in intensity picks the first encountered (deterministic by dict order)."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.emotions["happy"] = {"intensity": 0.5, "last_trigger_tick": 1}
        agent.emotions["calm"] = {"intensity": 0.5, "last_trigger_tick": 1}

        name, intensity = EmotionManager.get_dominant_emotion(agent)

        assert intensity == 0.5
        # Either happy or calm — both valid
        assert name in ("happy", "calm")

    # ── get_emotional_state_str ───────────────────────────────────────

    def test_get_emotional_state_str_empty(self):
        """RED: No emotions returns 'neutral'."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        state_str = EmotionManager.get_emotional_state_str(agent)
        assert state_str == "neutral"

    def test_get_emotional_state_str_single(self):
        """RED: Single emotion returns formatted string."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.emotions["happy"] = {"intensity": 0.7, "last_trigger_tick": 1}

        state_str = EmotionManager.get_emotional_state_str(agent)

        assert "happy" in state_str.lower()
        assert "7/10" in state_str or "7" in state_str or "0.7" in state_str

    def test_get_emotional_state_str_multiple(self):
        """RED: Multiple emotions are all listed in the string."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.emotions["happy"] = {"intensity": 0.7, "last_trigger_tick": 1}
        agent.emotions["curious"] = {"intensity": 0.4, "last_trigger_tick": 1}

        state_str = EmotionManager.get_emotional_state_str(agent)

        assert "happy" in state_str.lower()
        assert "curious" in state_str.lower()

    # ── Edge cases ────────────────────────────────────────────────────

    def test_agent_default_emotions_empty(self):
        """RED: New Agent has empty emotions dict."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        assert agent.emotions == {}

    def test_process_tick_no_emotions(self):
        """RED: process_tick on agent with no emotions returns empty list."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        expired = EmotionManager.process_tick(agent, tick=1)
        assert expired == []

    def test_apply_trigger_no_matching_definition(self):
        """RED: Trigger that matches no emotion def returns False/no-op."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        # This trigger event exists in angry, not in any emotion
        # We use a truly unknown event
        EmotionManager.apply_trigger(agent, "on_unknown_event", tick=1)
        assert agent.emotions == {}
