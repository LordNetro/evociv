"""Status effect system — apply, tick, expire, and stack effects on agents."""

from __future__ import annotations

from typing import Optional

from app.simulation.agent import Agent
from app.core.definitions import DEFINITIONS


class StatusEffectManager:
    """Pure static methods for status effect management."""

    @staticmethod
    def apply(agent: Agent, effect_name: str, source: Optional[str] = None) -> bool:
        """Apply a status effect to an agent. Returns True if applied/refreshed."""
        effect_def = DEFINITIONS.status_effects.get(effect_name)
        if not effect_def:
            return False

        existing = agent.active_effects.get(effect_name)

        if existing:
            # Refresh duration (additive up to max)
            existing["remaining_ticks"] = min(
                existing["remaining_ticks"] + effect_def.duration,
                effect_def.duration * effect_def.max_stacks,
            )
            # Increment stacks up to max
            existing["current_stacks"] = min(
                existing.get("current_stacks", 1) + 1,
                effect_def.max_stacks,
            )
        else:
            agent.active_effects[effect_name] = {
                "remaining_ticks": effect_def.duration,
                "current_stacks": 1,
                "total_duration": effect_def.duration,
            }

        return True

    @staticmethod
    def process_tick(agent: Agent) -> list[str]:
        """Process one tick for all active effects. Returns list of expired effects."""
        expired = []

        for effect_name, effect_data in list(agent.active_effects.items()):
            effect_data["remaining_ticks"] -= 1

            if effect_data["remaining_ticks"] <= 0:
                expired.append(effect_name)
                del agent.active_effects[effect_name]

        return expired

    @staticmethod
    def get_total_modifiers(agent: Agent) -> dict[str, float]:
        """Aggregate all active effect modifiers into a single dict.

        Rules:
        - Same effect type: strongest-wins
        - Different categories: all additive
        """
        aggregated = {}

        for effect_name, effect_data in agent.active_effects.items():
            effect_def = DEFINITIONS.status_effects.get(effect_name)
            if not effect_def:
                continue

            stacks = effect_data.get("current_stacks", 1)

            for attr, delta in effect_def.modifiers.items():
                # Strongest-wins for same attribute
                total_delta = delta * stacks
                if attr not in aggregated or abs(total_delta) > abs(aggregated[attr]):
                    aggregated[attr] = total_delta

        return aggregated

    @staticmethod
    def has_effect(agent: Agent, effect_name: str) -> bool:
        """Check if agent has a specific active effect."""
        return effect_name in agent.active_effects

    @staticmethod
    def remove_effect(agent: Agent, effect_name: str) -> bool:
        """Remove a specific effect. Returns True if it was active."""
        if effect_name in agent.active_effects:
            del agent.active_effects[effect_name]
            return True
        return False

    @staticmethod
    def clear_all(agent: Agent) -> None:
        """Remove all active effects."""
        agent.active_effects.clear()
