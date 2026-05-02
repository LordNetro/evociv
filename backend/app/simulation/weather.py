"""Weather system — state machine with transitions and effect application.

Drives weather changes over time, applies status effects (Wet, Chilled,
Overheated) and emotion triggers to agents based on their shelter protection.
Shelter uses exponential falloff: ``effective_mult = 1.0 - (protection²)``.
"""

from __future__ import annotations

import random

from app.core.definitions import DEFINITIONS
from app.simulation.agent import Agent


class WeatherSystem:
    """Manages weather state, transitions, and per-agent effect calculation.

    Current weather is tracked as a string key into ``DEFINITIONS.weather``.
    Each weather type has a random duration within ``(duration_min, duration_max)``.
    Transitions are weighted random choices from the weather's ``transitions`` dict.
    """

    def __init__(self, initial_weather: str = "clear"):
        self.current_weather: str = initial_weather
        weather_def = self._get_current_def()
        if weather_def:
            self.remaining_ticks: int = random.randint(
                weather_def.duration_min, weather_def.duration_max
            )
        else:
            self.remaining_ticks = 100

    def _get_current_def(self):
        """Return the ``WeatherDef`` for the current weather, or ``None``."""
        return DEFINITIONS.weather.get(self.current_weather)

    def _shelter_multiplier(self, protection: float) -> float:
        """Calculate effective exposure multiplier from shelter protection.

        Uses exponential falloff: ``1.0 - (protection²)``.

        Args:
            protection: Shelter protection value (0.0 to 1.0).

        Returns:
            Effective exposure multiplier — 1.0 means fully exposed,
            0.0 means fully protected.
        """
        return 1.0 - (protection * protection)

    def _transition(self) -> None:
        """Transition to a new weather type using weighted random selection.

        Reads the current weather's ``transitions`` dict (next_weather → weight)
        and uses ``random.choices`` for weighted selection. Falls back to ``"clear"``
        if the current weather has no transitions defined.
        """
        weather_def = self._get_current_def()
        if not weather_def or not weather_def.transitions:
            self.current_weather = "clear"
        else:
            choices = list(weather_def.transitions.keys())
            weights = list(weather_def.transitions.values())
            self.current_weather = random.choices(choices, weights=weights, k=1)[0]

        new_def = self._get_current_def()
        if new_def:
            self.remaining_ticks = random.randint(new_def.duration_min, new_def.duration_max)
        else:
            self.remaining_ticks = 100

    def tick(self, agents: list[Agent] | None = None, world=None, tick: int | None = None) -> dict:
        """Advance weather by one tick.

        Decrements ``remaining_ticks``. If it reaches 0, a transition occurs.
        If *agents* is provided, status effects and emotion triggers are
        applied based on shelter protection.

        Args:
            agents: Optional list of agents to apply weather effects to.
            world: Optional World (for shelter lookups).
            tick: Current simulation tick (for emotion cooldown tracking).

        Returns:
            A dict ``{"weather_changed": bool, "previous": str, "current": str}``
            indicating whether a transition occurred.
        """
        result: dict = {"weather_changed": False, "previous": self.current_weather, "current": self.current_weather}

        if self.remaining_ticks <= 0:
            self._transition()
            result["weather_changed"] = True
            result["current"] = self.current_weather

        self.remaining_ticks -= 1

        # Apply effects to agents if provided
        if agents is not None and world is not None:
            self._apply_weather_to_agents(agents, world, tick=tick)

        return result

    def _apply_weather_to_agents(self, agents: list[Agent], world, tick: int | None = None) -> None:
        """Apply weather status effects and emotion triggers to all agents."""
        from app.simulation.status_effects import StatusEffectManager
        from app.simulation.emotions import EmotionManager

        weather_def = self._get_current_def()
        if not weather_def:
            return

        emotion_tick = tick if tick is not None else 0

        for agent in agents:
            # Calculate shelter multiplier
            shelter_mult = self._get_agent_shelter(agent, world)

            # Apply status effects based on shelter exposure
            if shelter_mult > 0 and weather_def.status_effects_to_apply:
                for effect_name in weather_def.status_effects_to_apply:
                    StatusEffectManager.apply(agent, effect_name, source="weather")

            # Apply emotion triggers
            for trigger_key in weather_def.emotion_triggers:
                EmotionManager.apply_trigger(agent, trigger_key, emotion_tick)

    def _get_agent_shelter(self, agent: Agent, world) -> float:
        """Calculate the effective shelter multiplier for an agent.

        Checks for structures at the agent's position and uses the best
        ``shelter_protection`` value. Also checks for ``weather_resistance``
        skill modifier.

        Args:
            agent: The agent to check.
            world: The simulation world.

        Returns:
            Effective shelter multiplier (0.0 = full protection, 1.0 = exposed).
        """
        best_protection = 0.0

        # Check structures at agent's position
        if world:
            ax, ay = int(agent.position[0]), int(agent.position[1])
            structure = world.structures.get_structure_at((ax, ay))
            if structure is not None:
                struct_def = DEFINITIONS.structures.get(structure.structure_type)
                if struct_def is not None:
                    best_protection = max(best_protection, struct_def.shelter_protection)

            # Also check nearby structures within 1 tile
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    if dx == 0 and dy == 0:
                        continue
                    nearby = world.structures.get_structure_at((ax + dx, ay + dy))
                    if nearby is not None:
                        struct_def = DEFINITIONS.structures.get(nearby.structure_type)
                        if struct_def is not None:
                            best_protection = max(best_protection, struct_def.shelter_protection)

        # Apply weather_resistance from survival skill
        from app.simulation.skills import SkillManager
        weather_resist = SkillManager.get_weather_resistance(agent)
        best_protection = min(1.0, best_protection + weather_resist)

        return self._shelter_multiplier(best_protection)

    def get_effects_for_agent(self, agent: Agent, shelter_mult: float) -> dict[str, float]:
        """Return weather effects for an agent, scaled by shelter protection.

        Args:
            agent: The agent (used to check for skill-based resistance).
            world: The simulation world.

        Returns:
            Dict of effect modifiers (e.g. ``{"speed_multiplier": 0.85}``).
            Empty dict if no weather effects apply or full shelter.
        """
        if shelter_mult <= 0.0:
            return {}

        weather_def = self._get_current_def()
        if not weather_def or not weather_def.effects:
            return {}

        scaled = {}
        for key, value in weather_def.effects.items():
            # Interpolate toward 1.0 based on shelter
            if value < 1.0:
                scaled[key] = 1.0 - (1.0 - value) * shelter_mult
            elif value > 1.0:
                scaled[key] = 1.0 + (value - 1.0) * shelter_mult
            else:
                scaled[key] = 1.0

        return scaled

    def get_status_effects_to_apply(self) -> list[str]:
        """Return the list of status effect names for the current weather."""
        weather_def = self._get_current_def()
        if not weather_def:
            return []
        return list(weather_def.status_effects_to_apply)

    def get_emotion_triggers(self) -> dict[str, float]:
        """Return the emotion trigger keys for the current weather."""
        weather_def = self._get_current_def()
        if not weather_def:
            return {}
        return dict(weather_def.emotion_triggers)

    def get_weather_state(self) -> dict:
        """Return the current weather state as a dict (for snapshots).

        Returns:
            ``{"current_weather": str, "remaining_ticks": int, "category": str}``
        """
        weather_def = self._get_current_def()
        return {
            "current_weather": self.current_weather,
            "remaining_ticks": self.remaining_ticks,
            "category": weather_def.category if weather_def else "fair",
        }
