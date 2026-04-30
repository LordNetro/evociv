"""Tests for role configuration and helpers."""

import pytest

from app.simulation.agent import Agent
from app.simulation.actions import ActionType


class TestRolesHelpers:
    def test_get_role_config_known(self):
        """get_role_config returns config for known roles."""
        from app.simulation.roles import get_role_config
        config = get_role_config("miner")
        assert config["stat_modifiers"]["strength"] == 10

    def test_get_role_config_unknown_fallback(self):
        """get_role_config falls back to DEFAULT_ROLE for unknown roles."""
        from app.simulation.roles import get_role_config
        config = get_role_config("unknown_role")
        assert config == get_role_config("gatherer")

    def test_apply_role_stats(self):
        """apply_role_stats modifies agent stats according to role."""
        from app.simulation.roles import apply_role_stats
        agent = Agent(id="test_001", name="Test", position=(0.0, 0.0), role="fighter")
        apply_role_stats(agent)
        assert agent.strength == 65  # 50 + 15
        assert agent.speed == 55  # 50 + 5

    def test_apply_role_stats_no_negative(self):
        """apply_role_stats clamps stats to non-negative."""
        from app.simulation.roles import apply_role_stats
        agent = Agent(id="test_002", name="Test", position=(0.0, 0.0), role="gatherer")
        agent.speed = 0
        apply_role_stats(agent)
        assert agent.speed == 5  # 0 + 5

    def test_role_allows_action_allowed(self):
        """role_allows_action returns True for allowed actions."""
        from app.simulation.roles import role_allows_action
        assert role_allows_action("gatherer", ActionType.GATHER) is True
        assert role_allows_action("gatherer", "gather") is True

    def test_role_allows_action_blocked(self):
        """role_allows_action returns False for disallowed actions."""
        from app.simulation.roles import role_allows_action
        assert role_allows_action("scout", "attack") is False

    def test_role_allows_action_unknown_role_fallback(self):
        """Unknown role falls back to gatherer for action checks."""
        from app.simulation.roles import role_allows_action
        assert role_allows_action("nonexistent", ActionType.GATHER) is True

    def test_apply_role_stats_sets_role_data(self):
        """apply_role_stats populates agent.role_data with role config."""
        from app.simulation.roles import apply_role_stats
        agent = Agent(id="test_003", name="Test", position=(0.0, 0.0), role="miner")
        apply_role_stats(agent)
        assert hasattr(agent, "role_data")
        assert agent.role_data["stat_modifiers"]["strength"] == 10

    def test_apply_role_stats_role_data_fallback(self):
        """apply_role_stats falls back to default role for unknown roles."""
        from app.simulation.roles import apply_role_stats, get_role_config
        agent = Agent(id="test_004", name="Test", position=(0.0, 0.0), role="unknown")
        apply_role_stats(agent)
        assert agent.role_data == get_role_config("gatherer")


class TestRolesConfig:
    def test_roles_has_all_ten_entries(self):
        """ROLES dict contains all 10 expected roles."""
        from config.roles import ROLES
        expected = {
            "gatherer", "hunter", "fisher", "farmer", "miner",
            "builder", "crafter", "scout", "fighter", "healer",
        }
        assert set(ROLES.keys()) == expected

    def test_default_role(self):
        """DEFAULT_ROLE is gatherer."""
        from config.roles import DEFAULT_ROLE
        assert DEFAULT_ROLE == "gatherer"

    def test_each_role_has_required_keys(self):
        """Every role config contains priorities, allowed_actions, stat_modifiers."""
        from config.roles import ROLES
        for role_name, config in ROLES.items():
            assert "priorities" in config, f"{role_name} missing priorities"
            assert "allowed_actions" in config, f"{role_name} missing allowed_actions"
            assert "stat_modifiers" in config, f"{role_name} missing stat_modifiers"
            assert isinstance(config["priorities"], list)
            assert isinstance(config["allowed_actions"], list)
            assert isinstance(config["stat_modifiers"], dict)

    def test_role_priorities_format(self):
        """Priorities are list of (action_name, score) tuples with score 0-100."""
        from config.roles import ROLES
        for role_name, config in ROLES.items():
            for item in config["priorities"]:
                assert isinstance(item, tuple) and len(item) == 2, f"{role_name} bad priority item"
                action_name, score = item
                assert isinstance(action_name, str)
                assert isinstance(score, (int, float))
                assert 0 <= score <= 100, f"{role_name} priority {action_name} score {score} out of range"

    def test_gatherer_allowed_actions(self):
        """Gatherer can perform basic survival actions."""
        from config.roles import ROLES
        gatherer = ROLES["gatherer"]
        assert "gather" in gatherer["allowed_actions"]
        assert "eat" in gatherer["allowed_actions"]
        assert "drink" in gatherer["allowed_actions"]
        assert "rest" in gatherer["allowed_actions"]

    def test_fighter_allowed_actions(self):
        """Fighter can attack and basic survival actions."""
        from config.roles import ROLES
        fighter = ROLES["fighter"]
        assert "attack" in fighter["allowed_actions"] or "move" in fighter["allowed_actions"]

    def test_scout_has_explore_priority(self):
        """Scout prioritizes explore action."""
        from config.roles import ROLES
        scout = ROLES["scout"]
        actions = [a for a, _ in scout["priorities"]]
        assert "explore" in actions

    def test_miner_has_mine_priority(self):
        """Miner prioritizes mine action."""
        from config.roles import ROLES
        miner = ROLES["miner"]
        actions = [a for a, _ in miner["priorities"]]
        assert "mine" in actions
