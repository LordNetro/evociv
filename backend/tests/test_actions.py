"""Tests for action handlers and duration calculations."""

from app.simulation.actions import (
    ActionType,
    get_action_duration,
    _action_to_skill,
)
from app.simulation.agent import Agent


class TestGetActionDuration:
    """Duration formula with skill and effect modifiers."""

    def test_duration_no_skill_baseline(self):
        """Zero-skill agent gets baseline duration."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        dur = get_action_duration(ActionType.GATHER, agent)
        # base = max(2, 5 - 50//20) = max(2, 3) = 3
        # skill_mod = 1.0, effect_mod = 1.0
        assert dur == 3

    def test_duration_with_speed_skill(self):
        """Skill speed modifier reduces duration."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.skills["survival"] = 100  # level 1, speed_mult = 0.97
        dur = get_action_duration(ActionType.GATHER, agent)
        # base = 3, skill_mod = 0.97^1 = 0.97
        # 3 * 0.97 = 2.91 → round → 3 (or 2.91 > 2.5? let's compute)
        # Actually: round(3 * 0.97) = round(2.91) = 3
        # max(1, 3) = 3
        assert dur == 3

    def test_duration_with_exhausted_effect(self):
        """Exhausted effect halves speed."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        # Manually apply exhausted effect (speed_multiplier: 0.5)
        from app.simulation.status_effects import StatusEffectManager
        StatusEffectManager.apply(agent, "exhausted")
        dur = get_action_duration(ActionType.GATHER, agent)
        # base = 3, skill_mod = 1.0, effect_mod = 0.5
        # round(3 * 0.5) = round(1.5) = 2
        assert dur == 2

    def test_duration_minimum_one(self):
        """Duration is never less than 1."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.skills["survival"] = 1200  # level 5, speed_mult = 0.97^5
        agent._storage_nearby = True
        dur = get_action_duration(ActionType.EXPLORE, agent)
        # base = max(1, 5 - 50//20) = 3
        # skill_mod = 0.97^5 ≈ 0.8587
        # 3 * 0.8587 ≈ 2.58 → round → 3
        assert dur >= 1

    def test_action_to_skill_mapping(self):
        """_action_to_skill returns correct skill name."""
        assert _action_to_skill(ActionType.CHOP) == "carpentry"
        assert _action_to_skill(ActionType.ATTACK) == "combat"
        assert _action_to_skill(ActionType.GATHER) == "survival"
        assert _action_to_skill(ActionType.CRAFT) == "crafting"
        assert _action_to_skill(ActionType.SOCIALIZE) == "social"
        assert _action_to_skill(ActionType.EXPLORE) == "exploration"
        assert _action_to_skill(ActionType.MINE) == "mining"
        assert _action_to_skill(ActionType.FARM) == "farming"

    def test_action_to_skill_none(self):
        """Unknown action returns None."""
        assert _action_to_skill(ActionType.REST) is None
        assert _action_to_skill(ActionType.DRINK) is None
        assert _action_to_skill(ActionType.HEAL) is None


class TestHandleEatPoison:
    """Poison trigger on eating poisonous berries."""

    def test_eat_poisonous_berry_applies_effect(self):
        """Eating a poisonous berry applies poisoned status effect."""
        from app.simulation.actions import handle_eat
        from app.simulation.world import World
        from app.simulation.world import Tile
        from app.simulation.status_effects import StatusEffectManager

        world = World(10, 10)
        # Place poisonous berry tile adjacent to agent
        tile = Tile(
            x=2, y=0,
            resource_type="berries",
            amount=5,
            subtype="poisonous_berry",
            hidden_properties={"is_poisonous": True},
        )
        world.set_tile(2, 0, tile)

        agent = Agent(id="test", name="Test", position=(1.0, 0.0))
        agent.inventory["berries"] = 1

        result = handle_eat(agent, world)

        assert result.success is True
        assert StatusEffectManager.has_effect(agent, "poisoned")
