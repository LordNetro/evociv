"""Tests for the combat system."""


from app.simulation.combat import CombatManager


class TestCombatManager:
    def test_melee_damage_spear_vs_hide_armor(self):
        """Melee damage with spear vs hide_armor."""
        # spear: damage 15, hide_armor: damage_reduction 10
        # strength 60 -> max(1, 15 + 60*0.2 - 10*0.5) = max(1, 15 + 12 - 5) = 22
        dmg = CombatManager.calculate_melee_damage(60, 15, 10)
        assert dmg == 22

    def test_ranged_damage_bow(self):
        """Ranged damage with bow."""
        # bow: damage 12, armor 5
        # intelligence 50 -> max(1, 12 + 50*0.1 - 5*0.3) = max(1, 12 + 5 - 1.5) = 15.5
        dmg = CombatManager.calculate_ranged_damage(50, 12, 5)
        assert dmg == 15.5

    def test_guard_halves_damage(self):
        """Guarding halves incoming damage."""
        dmg = CombatManager.calculate_damage_with_guard(20, True)
        assert dmg == 10.0

    def test_guard_no_mitigation(self):
        """Not guarding leaves damage unchanged."""
        dmg = CombatManager.calculate_damage_with_guard(20, False)
        assert dmg == 20.0

    def test_melee_damage_clamped_minimum(self):
        """Melee damage minimum is 1."""
        dmg = CombatManager.calculate_melee_damage(1, 1, 100)
        assert dmg == 1.0

    def test_ranged_damage_clamped_minimum(self):
        """Ranged damage minimum is 1."""
        dmg = CombatManager.calculate_ranged_damage(1, 1, 100)
        assert dmg == 1.0

    def test_get_weapon_stats_spear(self):
        """Weapon lookup returns correct data."""
        stats = CombatManager.get_weapon_stats("spear")
        assert stats["damage"] == 15
        assert stats["type"] == "melee"
        assert stats["ranged"] is False

    def test_get_weapon_stats_bow(self):
        """Bow lookup returns ranged data."""
        stats = CombatManager.get_weapon_stats("bow")
        assert stats["damage"] == 12
        assert stats["type"] == "ranged"
        assert stats["ranged"] is True
        assert stats["ammo"] == "arrows"
        assert stats["max_range"] == 5

    def test_get_weapon_stats_invalid(self):
        """Invalid weapon returns empty dict."""
        stats = CombatManager.get_weapon_stats("nonexistent")
        assert stats == {}

    def test_get_armor_stats_hide(self):
        """Armor lookup returns correct data."""
        stats = CombatManager.get_armor_stats("hide_armor")
        assert stats["damage_reduction"] == 10

    def test_get_armor_stats_none(self):
        """No armor returns 0 reduction."""
        stats = CombatManager.get_armor_stats("none")
        assert stats["damage_reduction"] == 0

    def test_get_armor_stats_invalid(self):
        """Invalid armor returns empty dict."""
        stats = CombatManager.get_armor_stats("nonexistent")
        assert stats == {}

    def test_melee_damage_zero_strength(self):
        """Melee damage with zero strength relies on weapon only."""
        dmg = CombatManager.calculate_melee_damage(0, 15, 5)
        assert dmg == max(1.0, 15 + 0 - 2.5)

    def test_ranged_damage_zero_intelligence(self):
        """Ranged damage with zero intelligence relies on weapon only."""
        dmg = CombatManager.calculate_ranged_damage(0, 12, 5)
        assert dmg == max(1.0, 12 + 0 - 1.5)

    def test_weapon_lookup_empty_string(self):
        """Empty string weapon returns empty dict."""
        stats = CombatManager.get_weapon_stats("")
        assert stats == {}
