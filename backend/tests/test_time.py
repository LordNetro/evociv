"""Tests for the TimeSystem — day/night cycle.

Written FIRST (TDD RED phase), TimeSystem does not yet exist.
"""

from app.simulation.time import TimeSystem


class TestTimeSystem:
    """TDD Cycle for TimeSystem."""

    def test_initial_state(self):
        """RED: TimeSystem starts at tick 0 of day 0, daytime."""
        ts = TimeSystem()
        assert ts.tick_count_of_day == 0
        assert ts.day_count == 0
        assert ts.is_night is False

    def test_tick_increments_tick_count(self):
        """RED: Calling tick() increments tick_count_of_day by 1."""
        ts = TimeSystem()
        ts.tick()
        assert ts.tick_count_of_day == 1
        assert ts.day_count == 0

    def test_tick_wraps_at_day_length(self):
        """RED: When tick_count_of_day reaches day_length_ticks, it wraps to 0 and day increments."""
        ts = TimeSystem(day_length_ticks=5, daylight_ticks=3)
        for _ in range(5):
            ts.tick()
        assert ts.tick_count_of_day == 0
        assert ts.day_count == 1

    def test_is_night_after_daylight_ticks(self):
        """RED: is_night is True when tick_count_of_day >= daylight_ticks."""
        ts = TimeSystem(day_length_ticks=10, daylight_ticks=6)
        for _ in range(6):
            ts.tick()
        assert ts.is_night is True

    def test_is_night_false_during_day(self):
        """RED: is_night is False during daylight hours."""
        ts = TimeSystem(day_length_ticks=10, daylight_ticks=6)
        for _ in range(5):
            ts.tick()
        assert ts.is_night is False

    def test_night_ends_at_day_wrap(self):
        """RED: After day wraps, is_night returns to False."""
        ts = TimeSystem(day_length_ticks=5, daylight_ticks=3)
        # Day: ticks 0-2, Night: ticks 3-4
        for _ in range(5):
            ts.tick()
        assert ts.is_night is False  # Back to start of day

    def test_time_of_day_label_day(self):
        """RED: During day, time_of_day_label returns 'Daytime'."""
        ts = TimeSystem(day_length_ticks=10, daylight_ticks=6)
        assert ts.time_of_day_label == "Daytime"

    def test_time_of_day_label_night(self):
        """RED: During night, time_of_day_label returns 'Nighttime'."""
        ts = TimeSystem(day_length_ticks=10, daylight_ticks=6)
        for _ in range(6):
            ts.tick()
        assert ts.time_of_day_label == "Nighttime"

    def test_get_night_multiplier_daytime(self):
        """RED: During day, get_night_multiplier returns 1.0 for any stat."""
        ts = TimeSystem(day_length_ticks=10, daylight_ticks=6)
        assert ts.get_night_multiplier("resource_regen_multiplier") == 1.0
        assert ts.get_night_multiplier("thirst_decay_multiplier") == 1.0

    def test_get_night_multiplier_night_known(self):
        """RED: During night, known stat multipliers return configured values."""
        ts = TimeSystem(day_length_ticks=10, daylight_ticks=6)
        for _ in range(6):
            ts.tick()
        assert ts.is_night is True
        val = ts.get_night_multiplier("resource_regen_multiplier")
        # Value comes from simulation config; we just check it's not 1.0
        assert val != 1.0

    def test_get_night_multiplier_night_unknown(self):
        """RED: During night, unknown stat returns 1.0."""
        ts = TimeSystem(day_length_ticks=10, daylight_ticks=6)
        for _ in range(6):
            ts.tick()
        assert ts.get_night_multiplier("nonexistent_stat") == 1.0

    def test_custom_day_length(self):
        """RED: TimeSystem accepts custom day_length_ticks."""
        ts = TimeSystem(day_length_ticks=100, daylight_ticks=60)
        assert ts.day_length_ticks == 100
        assert ts.daylight_ticks == 60
        assert ts.night_ticks == 40

    def test_multiple_day_cycles(self):
        """RED: Multiple full day cycles increment day_count correctly."""
        ts = TimeSystem(day_length_ticks=50, daylight_ticks=30)
        for _ in range(150):  # 3 full days
            ts.tick()
        assert ts.day_count == 3
        assert ts.tick_count_of_day == 0
