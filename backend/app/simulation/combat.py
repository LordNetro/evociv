"""Combat system: damage calculation, weapon/armor tables."""

from __future__ import annotations

from app.core.definitions import DEFINITIONS


# Module-level aliases for backward compatibility — data now lives in DEFINITIONS
WEAPONS: dict[str, dict] = {name: w.model_dump() for name, w in DEFINITIONS.weapons.items()}
ARMOR: dict[str, dict] = {name: a.model_dump() for name, a in DEFINITIONS.armor.items()}


class CombatManager:
    """Pure static methods for combat calculations."""

    @staticmethod
    def calculate_melee_damage(attacker_strength: float, weapon_damage: float, defender_armor: float) -> float:
        """Calculate melee damage.

        Formula: max(1, weapon_damage + attacker_strength * 0.2 - defender_armor * 0.5)
        """
        return max(1.0, weapon_damage + attacker_strength * 0.2 - defender_armor * 0.5)

    @staticmethod
    def calculate_ranged_damage(attacker_intelligence: float, weapon_damage: float, defender_armor: float) -> float:
        """Calculate ranged damage.

        Formula: max(1, weapon_damage + attacker_intelligence * 0.1 - defender_armor * 0.3)
        """
        return max(1.0, weapon_damage + attacker_intelligence * 0.1 - defender_armor * 0.3)

    @staticmethod
    def calculate_melee_damage_with_effects(attacker: Agent, weapon_damage: float, defender_armor: float) -> float:
        """Calculate melee damage with skill, status effect, and emotion modifiers.

        Uses the same base formula as calculate_melee_damage but multiplies
        by combat skill modifier and status effect/emotion damage modifiers.
        """
        base = max(1.0, weapon_damage + attacker.strength * 0.2 - defender_armor * 0.5)
        from app.simulation.skills import SkillManager
        from app.simulation.status_effects import StatusEffectManager
        from app.simulation.emotions import EmotionManager
        skill_mod = SkillManager.get_combat_modifier(attacker, "combat")
        effect_mod = StatusEffectManager.get_total_modifiers(attacker).get("damage_multiplier", 1.0)
        emotion_mod = EmotionManager.get_total_modifiers(attacker).get("damage_multiplier", 1.0)
        return max(1.0, base * skill_mod * effect_mod * emotion_mod)

    @staticmethod
    def calculate_ranged_damage_with_effects(attacker: Agent, weapon_damage: float, defender_armor: float) -> float:
        """Calculate ranged damage with skill, status effect, and emotion modifiers."""
        base = max(1.0, weapon_damage + attacker.intelligence * 0.1 - defender_armor * 0.3)
        from app.simulation.skills import SkillManager
        from app.simulation.status_effects import StatusEffectManager
        from app.simulation.emotions import EmotionManager
        skill_mod = SkillManager.get_combat_modifier(attacker, "combat")
        effect_mod = StatusEffectManager.get_total_modifiers(attacker).get("damage_multiplier", 1.0)
        emotion_mod = EmotionManager.get_total_modifiers(attacker).get("damage_multiplier", 1.0)
        return max(1.0, base * skill_mod * effect_mod * emotion_mod)

    @staticmethod
    def get_weapon_stats(weapon_name: str) -> dict:
        """Return weapon data from DEFINITIONS."""
        weapon = DEFINITIONS.weapons.get(weapon_name)
        if weapon is None:
            return {}
        return weapon.model_dump()

    @staticmethod
    def get_armor_stats(armor_name: str) -> dict:
        """Return armor data from DEFINITIONS."""
        armor = DEFINITIONS.armor.get(armor_name)
        if armor is None:
            return {}
        return armor.model_dump()

    @staticmethod
    def calculate_damage_with_guard(damage: float, is_guarding: bool) -> float:
        """Apply guard mitigation: if guarding, damage *= 0.5."""
        if is_guarding:
            return damage * 0.5
        return damage


__all__ = ["CombatManager", "WEAPONS", "ARMOR"]
