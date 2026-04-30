"""Combat system: damage calculation, weapon/armor tables."""

from __future__ import annotations


WEAPONS: dict[str, dict] = {
    "fist": {
        "damage": 5,
        "type": "melee",
        "ranged": False,
        "ammo": None,
    },
    "spear": {
        "damage": 15,
        "type": "melee",
        "ranged": False,
        "ammo": None,
    },
    "bow": {
        "damage": 12,
        "type": "ranged",
        "ranged": True,
        "ammo": "arrows",
        "max_range": 5,
    },
    "iron_sword": {
        "damage": 25,
        "type": "melee",
        "ranged": False,
        "ammo": None,
    },
}


ARMOR: dict[str, dict] = {
    "none": {
        "damage_reduction": 0,
    },
    "fiber_armor": {
        "damage_reduction": 5,
    },
    "hide_armor": {
        "damage_reduction": 10,
    },
}


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
    def get_weapon_stats(weapon_name: str) -> dict:
        """Return weapon data from WEAPONS table."""
        return WEAPONS.get(weapon_name, {}).copy()

    @staticmethod
    def get_armor_stats(armor_name: str) -> dict:
        """Return armor data from ARMOR table."""
        return ARMOR.get(armor_name, {}).copy()

    @staticmethod
    def calculate_damage_with_guard(damage: float, is_guarding: bool) -> float:
        """Apply guard mitigation: if guarding, damage *= 0.5."""
        if is_guarding:
            return damage * 0.5
        return damage


__all__ = ["CombatManager", "WEAPONS", "ARMOR"]
