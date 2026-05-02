"""Skill progression system — XP award, level-up, and modifier computation."""

from __future__ import annotations

from app.simulation.agent import Agent
from app.core.definitions import DEFINITIONS

# XP thresholds: level -> cumulative XP needed
XP_CURVE = {
    1: 100,
    2: 250,
    3: 500,
    4: 800,
    5: 1200,
    6: 1800,
    7: 2500,
    8: 3500,
    9: 5000,
    10: 7000,
}


class SkillManager:
    """Pure static methods for skill progression."""

    @staticmethod
    def award_xp(agent: Agent, action_type: str) -> dict[str, int]:
        """Award XP for completing an action. Returns dict of skills that leveled up."""
        leveled_up = {}
        for skill_name, skill_def in DEFINITIONS.skills.items():
            xp_gain = skill_def.base_xp_per_action.get(action_type, 0)
            if xp_gain == 0:
                continue

            current_xp = agent.skills.get(skill_name, 0)
            new_xp = current_xp + xp_gain
            agent.skills[skill_name] = new_xp

            # Check if leveled up
            current_level = SkillManager.get_level(current_xp)
            new_level = SkillManager.get_level(new_xp)
            if new_level > current_level:
                leveled_up[skill_name] = new_level

        return leveled_up

    @staticmethod
    def get_level(xp: int) -> int:
        """Get skill level from cumulative XP."""
        level = 0
        for lvl, threshold in sorted(XP_CURVE.items()):
            if xp >= threshold:
                level = lvl
            else:
                break
        return level

    @staticmethod
    def get_speed_modifier(agent: Agent, skill_name: str) -> float:
        """Get speed multiplier for a skill. 1.0 = normal speed, <1.0 = faster."""
        xp = agent.skills.get(skill_name, 0)
        level = SkillManager.get_level(xp)
        skill_def = DEFINITIONS.skills.get(skill_name)
        if skill_def and level > 0:
            mult = skill_def.effects_per_level.get("speed_multiplier", 1.0)
            return mult ** level  # compound: each level multiplies
        return 1.0

    @staticmethod
    def get_combat_modifier(agent: Agent, skill_name: str) -> float:
        """Get damage multiplier from combat skill. 1.0 = normal damage."""
        xp = agent.skills.get(skill_name, 0)
        level = SkillManager.get_level(xp)
        skill_def = DEFINITIONS.skills.get(skill_name)
        if skill_def and level > 0:
            mult = skill_def.effects_per_level.get("damage_multiplier", 1.0)
            return mult ** level
        return 1.0

    @staticmethod
    def get_crafting_quality(agent: Agent, skill_name: str) -> float:
        """Get quality multiplier from crafting skill."""
        xp = agent.skills.get(skill_name, 0)
        level = SkillManager.get_level(xp)
        skill_def = DEFINITIONS.skills.get(skill_name)
        if skill_def and level > 0:
            mult = skill_def.effects_per_level.get("quality_multiplier", 1.0)
            return mult ** level
        return 1.0

    @staticmethod
    def get_skill_level(agent: Agent, skill_name: str) -> int:
        """Get integer skill level."""
        xp = agent.skills.get(skill_name, 0)
        return SkillManager.get_level(xp)

    @staticmethod
    def get_weather_resistance(agent: Agent) -> float:
        """Get total weather resistance from skills.

        Reads the ``weather_resistance`` effect from each skill's
        ``effects_per_level`` and sums them multiplicatively.

        Returns:
            Total weather resistance value (adds to shelter protection).
        """
        total = 0.0
        for skill_name, skill_def in DEFINITIONS.skills.items():
            resist = skill_def.effects_per_level.get("weather_resistance", 0.0)
            if resist:
                xp = agent.skills.get(skill_name, 0)
                level = SkillManager.get_level(xp)
                if level > 0:
                    # Compound per level
                    total += resist * level
        return min(1.0, total)
