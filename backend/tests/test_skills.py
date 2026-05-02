"""Tests for the skill progression system."""

from app.simulation.agent import Agent
from app.simulation.skills import SkillManager


class TestSkillManager:
    """TDD Cycle for SkillManager — test first, then implement."""

    def test_xp_awarded_on_action(self):
        """RED: Award XP for a chop action to carpentry skill."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        assert agent.skills == {}

        leveled_up = SkillManager.award_xp(agent, "chop")

        assert agent.skills.get("carpentry") == 5
        assert leveled_up == {}  # no level-up at 5 XP

    def test_level_up_at_100_xp(self):
        """RED: After accumulating 100 XP, skill levels up."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.skills["carpentry"] = 95
        agent.skills["combat"] = 0

        leveled_up = SkillManager.award_xp(agent, "chop")  # 5 XP → 100

        assert agent.skills["carpentry"] == 100
        assert leveled_up == {"carpentry": 1}

    def test_get_level_zero(self):
        """RED: Level 0 when no XP."""
        assert SkillManager.get_level(0) == 0
        assert SkillManager.get_level(50) == 0

    def test_get_level_thresholds(self):
        """RED: Correct levels at thresholds."""
        assert SkillManager.get_level(100) == 1
        assert SkillManager.get_level(250) == 2
        assert SkillManager.get_level(500) == 3
        assert SkillManager.get_level(800) == 4
        assert SkillManager.get_level(1200) == 5

    def test_speed_modifier_baseline(self):
        """RED: Zero skill yields 1.0x speed modifier."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        mod = SkillManager.get_speed_modifier(agent, "carpentry")
        assert mod == 1.0

    def test_speed_modifier_with_skill(self):
        """RED: Skill level 5 with 0.95 per-level compound."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.skills["carpentry"] = 1200  # level 5
        mod = SkillManager.get_speed_modifier(agent, "carpentry")
        # 0.95 ** 5 ≈ 0.7738
        assert round(mod, 4) == 0.7738

    def test_combat_modifier_baseline(self):
        """RED: Zero combat skill yields 1.0x damage."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        mod = SkillManager.get_combat_modifier(agent, "combat")
        assert mod == 1.0

    def test_combat_modifier_with_skill(self):
        """RED: Combat level 3 with 1.10 per-level compound."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.skills["combat"] = 500  # level 3
        mod = SkillManager.get_combat_modifier(agent, "combat")
        # 1.10 ** 3 = 1.331
        assert round(mod, 3) == 1.331

    def test_crafting_quality_modifier(self):
        """RED: Crafting quality scales with skill level."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.skills["crafting"] = 500  # level 3
        mod = SkillManager.get_crafting_quality(agent, "crafting")
        # 1.10 ** 3 = 1.331
        assert round(mod, 3) == 1.331

    def test_skill_level_helper(self):
        """RED: get_skill_level returns correct integer level."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        assert SkillManager.get_skill_level(agent, "carpentry") == 0
        agent.skills["carpentry"] = 100
        assert SkillManager.get_skill_level(agent, "carpentry") == 1

    def test_xp_to_unknown_action(self):
        """RED: Unknown action type awards no XP."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        leveled_up = SkillManager.award_xp(agent, "nonexistent_action")
        assert leveled_up == {}
        assert agent.skills == {}

    def test_multiple_levels_at_once(self):
        """RED: Large XP gain can skip multiple levels."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        agent.skills["combat"] = 100  # level 1, needs 250 for level 2
        leveled_up = SkillManager.award_xp(agent, "attack")  # +20 XP
        assert leveled_up == {}  # 120 < 250, still level 1
        agent.skills["combat"] = 240
        leveled_up = SkillManager.award_xp(agent, "attack")  # 260 → level 2
        assert leveled_up == {"combat": 2}
