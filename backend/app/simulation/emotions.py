"""Emotion/morale system — float intensity model with tick decay and event triggers.

Mirrors ``StatusEffectManager`` pattern: pure static methods on ``EmotionManager``,
data-driven via ``emotions.yaml`` → ``EmotionDef``, new ``Agent.emotions`` dict field,
tick decay in engine loop, modifier aggregation composited multiplicatively with
skills + status effects.
"""

from __future__ import annotations

from app.core.definitions import DEFINITIONS
from app.simulation.agent import Agent

_COOLDOWN_TICKS = 5


class EmotionManager:
    """Pure static methods for emotion management.

    Each method takes an ``Agent`` instance and operates on ``agent.emotions``,
    a ``dict[str, dict]`` keyed by emotion name with ``{"intensity": float,
    "last_trigger_tick": int}`` values.
    """

    @staticmethod
    def apply_trigger(agent: Agent, event_type: str, tick: int) -> None:
        """Apply emotion triggers from *event_type* at *tick*.

        Finds all emotions whose ``triggers`` include *event_type*, adds the
        configured delta to the agent's intensity for that emotion (capped at
        ``1.0``), respecting a ``_COOLDOWN_TICKS``-tick cooldown per emotion
        per agent.

        Unknown events are silently ignored (no-op).
        """
        for emotion_name, emotion_def in DEFINITIONS.emotions.items():
            delta = emotion_def.triggers.get(event_type)
            if delta is None:
                continue

            existing = agent.emotions.get(emotion_name)

            # Cooldown check: skip if triggered within last _COOLDOWN_TICKS ticks
            if existing is not None:
                last_tick = existing.get("last_trigger_tick", -999)
                if tick - last_tick < _COOLDOWN_TICKS:
                    continue

            # Apply or update
            current_intensity = existing["intensity"] if existing else 0.0
            new_intensity = min(1.0, current_intensity + delta)
            agent.emotions[emotion_name] = {
                "intensity": new_intensity,
                "last_trigger_tick": tick,
            }

    @staticmethod
    def process_tick(agent: Agent, tick: int) -> list[str]:
        """Process one tick of decay for all active emotions.

        Decrements each emotion's intensity by its ``decay_per_tick``. Emotions
        that reach ``≤ 0`` are removed.

        Returns:
            A list of emotion names that expired this tick.
        """
        expired: list[str] = []

        for emotion_name, emotion_data in list(agent.emotions.items()):
            emotion_def = DEFINITIONS.emotions.get(emotion_name)
            decay = emotion_def.decay_per_tick if emotion_def else 0.005

            emotion_data["intensity"] -= decay

            if emotion_data["intensity"] <= 0:
                expired.append(emotion_name)
                del agent.emotions[emotion_name]

        return expired

    @staticmethod
    def get_total_modifiers(agent: Agent) -> dict[str, float]:
        """Aggregate all active emotion effects into a single dict.

        Rules (matches ``StatusEffectManager`` pattern):
        - Same effect attribute: strongest-wins (attribute whose value deviates
          farthest from ``1.0``)
        - Different attributes: all included
        - Empty emotions: returns ``{}``

        The returned modifier values are interpolated by the emotion's current
        intensity::

            effective_mod = 1.0 + (effect_value - 1.0) * intensity
        """
        aggregated: dict[str, float] = {}

        for emotion_name, emotion_data in agent.emotions.items():
            emotion_def = DEFINITIONS.emotions.get(emotion_name)
            if not emotion_def:
                continue

            intensity = emotion_data.get("intensity", 0.0)

            for attr, value in emotion_def.effects.items():
                # Linear interpolation toward effect value based on intensity
                effective = 1.0 + (value - 1.0) * intensity

                # Strongest-wins: keep the value that deviates farthest from 1.0
                if attr not in aggregated or abs(effective - 1.0) > abs(aggregated[attr] - 1.0):
                    aggregated[attr] = effective

        return aggregated

    @staticmethod
    def get_dominant_emotion(agent: Agent) -> tuple[str, float] | None:
        """Return ``(name, intensity)`` of the emotion with highest intensity.

        Returns ``None`` if the agent has no active emotions.

        Ties are broken by first-encountered (dict insertion order = Python 3.7+).
        """
        if not agent.emotions:
            return None

        dominant_name = max(
            agent.emotions,
            key=lambda name: agent.emotions[name]["intensity"],
        )
        return dominant_name, agent.emotions[dominant_name]["intensity"]

    @staticmethod
    def get_emotional_state_str(agent: Agent) -> str:
        """Format the agent's emotional state for LLM prompts.

        Returns a human-readable string like::

            Happy (7/10), Curious (4/10)

        Or ``"neutral"`` if no emotions are active.
        """
        if not agent.emotions:
            return "neutral"

        parts: list[str] = []
        # Sort by intensity descending so dominant emotion appears first
        for emotion_name, emotion_data in sorted(
            agent.emotions.items(),
            key=lambda item: item[1]["intensity"],
            reverse=True,
        ):
            # Scale 0.0-1.0 to 0-10 for LLM readability
            scaled = round(emotion_data["intensity"] * 10)
            parts.append(f"{emotion_name.title()} ({scaled}/10)")

        return ", ".join(parts)


__all__ = ["EmotionManager"]
