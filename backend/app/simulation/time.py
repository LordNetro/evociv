"""Time system — day/night cycle tracking.

Drives the simulation's temporal dimension: tick counting within a day,
day transitions, night detection, and stat multipliers for night effects.
"""

from __future__ import annotations

from app.core.definitions import DEFINITIONS


class TimeSystem:
    """Manages the day/night cycle and provides night stat multipliers.

    Tracks ticks within the current day (``tick_count_of_day``), the total
    number of completed days (``day_count``), and whether it is currently
    night (``is_night``). Night multipliers are read from the simulation
    YAML ``time.effects.night`` section.
    """

    def __init__(self, day_length_ticks: int | None = None, daylight_ticks: int | None = None):
        config = DEFINITIONS.time_config
        self.day_length_ticks = day_length_ticks or config.day_length_ticks
        self.daylight_ticks = daylight_ticks or config.daylight_ticks
        self.night_ticks = self.day_length_ticks - self.daylight_ticks
        self.tick_count_of_day: int = 0
        self.day_count: int = 0

    def tick(self) -> None:
        """Advance the time system by one tick.

        Increments ``tick_count_of_day``. When it reaches ``day_length_ticks``,
        it wraps to 0 and ``day_count`` increments.
        """
        self.tick_count_of_day += 1
        if self.tick_count_of_day >= self.day_length_ticks:
            self.tick_count_of_day = 0
            self.day_count += 1

    @property
    def is_night(self) -> bool:
        """Return ``True`` if the current tick is during nighttime."""
        return self.tick_count_of_day >= self.daylight_ticks

    @property
    def time_of_day_label(self) -> str:
        """Return ``"Daytime"`` or ``"Nighttime"`` based on current tick."""
        return "Nighttime" if self.is_night else "Daytime"

    def get_night_multiplier(self, stat: str) -> float:
        """Return the night multiplier for a given stat.

        Args:
            stat: The stat name (e.g. ``"resource_regen_multiplier"``,
                  ``"thirst_decay_multiplier"``, ``"energy_regen_multiplier"``,
                  ``"visibility_multiplier"``).

        Returns:
            The multiplier from config during night, or ``1.0`` during day
            or for unknown stats.
        """
        if not self.is_night:
            return 1.0
        night_config = DEFINITIONS.time_config.effects.get("night")
        if night_config is None:
            return 1.0
        return getattr(night_config, stat, 1.0)
