"""Tests for data-driven definitions: models, loader, and YAML content."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.core.definition_models import (
    ActionDef,
    AgentDefault,
    AgentDefaults,
    ArmorDef,
    DefinitionContainer,
    FactionDef,
    RecipeDef,
    ResourceDef,
    RoleDef,
    SimulationConfig,
    SkillDef,
    StatusEffectDef,
    StructureDef,
    TimeConfig,
    WeatherDef,
    WeaponDef,
)


# ===========================================================================
# Task 1.1: Pydantic Model Tests
# ===========================================================================


class TestResourceDef:
    def test_valid_resource(self):
        """A valid resource definition should instantiate without error."""
        r = ResourceDef(
            name="wood",
            category="natural",
            properties={"count": 80, "min_amount": 5, "max_amount": 15, "regen_rate": 0.01},
        )
        assert r.name == "wood"
        assert r.category == "natural"
        assert r.properties["count"] == 80

    def test_animal_resource(self):
        """An animal resource with sub_products."""
        r = ResourceDef(
            name="deer",
            category="animal",
            properties={
                "count": 10,
                "min_amount": 1,
                "max_amount": 3,
                "regen_rate": 0.02,
                "sub_products": ["hide", "bone", "meat"],
            },
        )
        assert r.name == "deer"
        assert r.properties["sub_products"] == ["hide", "bone", "meat"]

    def test_crafted_item(self):
        """A crafted item (output from a recipe)."""
        r = ResourceDef(name="stone_axe", category="crafted", properties={"stackable": False})
        assert r.name == "stone_axe"

    def test_subproduct(self):
        """A sub-product from hunting/animals."""
        r = ResourceDef(name="hide", category="subproduct", properties={"source": "deer"})
        assert r.properties["source"] == "deer"


class TestRecipeDef:
    def test_valid_recipe(self):
        """A valid recipe with all fields."""
        r = RecipeDef(
            name="stone_axe",
            inputs={"wood": 3, "stone": 2},
            output={"stone_axe": 1},
            duration=10,
            category="tool",
            modifiers={"chop_speed": 2, "attack_damage": 5},
        )
        assert r.name == "stone_axe"
        assert r.duration == 10

    def test_recipe_with_workbench(self):
        """A recipe requiring a workbench."""
        r = RecipeDef(
            name="spear",
            inputs={"wood": 4, "stone": 3},
            output={"spear": 1},
            workbench="basic",
            duration=15,
            category="weapon",
            modifiers={"attack_damage": 15, "hunt_bonus": 2},
        )
        assert r.workbench == "basic"
        assert r.workbench_level == 0  # default

    def test_recipe_minimal(self):
        """A minimal recipe (planks)."""
        r = RecipeDef(
            name="planks",
            inputs={"wood": 2},
            output={"planks": 2},
            duration=5,
            category="material",
        )
        assert r.workbench is None
        assert r.modifiers == {}


class TestWeaponDef:
    def test_melee_weapon(self):
        """A melee weapon (fist)."""
        w = WeaponDef(name="fist", damage=5, type="melee", ranged=False, ammo=None)
        assert w.damage == 5
        assert w.type == "melee"
        assert w.ranged is False
        assert w.ammo is None

    def test_ranged_weapon(self):
        """A ranged weapon (bow)."""
        w = WeaponDef(name="bow", damage=12, type="ranged", ranged=True, ammo="arrows", max_range=5)
        assert w.damage == 12
        assert w.type == "ranged"
        assert w.ranged is True
        assert w.ammo == "arrows"
        assert w.max_range == 5


class TestArmorDef:
    def test_armor(self):
        """An armor definition."""
        a = ArmorDef(name="hide_armor", damage_reduction=10)
        assert a.name == "hide_armor"
        assert a.damage_reduction == 10

    def test_no_armor(self):
        """No armor case."""
        a = ArmorDef(name="none", damage_reduction=0)
        assert a.damage_reduction == 0


class TestRoleDef:
    def test_gatherer_role(self):
        """A simple role with no priorities."""
        r = RoleDef(
            name="gatherer",
            description="A gatherer",
            priorities=[],
            allowed_actions=["move", "gather", "eat", "drink", "rest", "explore"],
            stat_modifiers={"speed": 5},
            tool_allowlist=[],
        )
        assert r.name == "gatherer"
        assert r.stat_modifiers == {"speed": 5}

    def test_hunter_role(self):
        """A role with priorities, modifiers, and tool allowlist."""
        r = RoleDef(
            name="hunter",
            description="A hunter",
            priorities=[("hunt", 80), ("gather", 60)],
            allowed_actions=["move", "hunt", "gather", "eat", "drink", "rest", "explore"],
            stat_modifiers={"strength": 10, "speed": 5},
            tool_allowlist=["spear"],
        )
        assert len(r.priorities) == 2
        assert r.priorities[0] == ("hunt", 80)
        assert r.tool_allowlist == ["spear"]


class TestFactionDef:
    def test_faction(self):
        """A faction with name and color."""
        f = FactionDef(name="River Clan", color="#00AAFF")
        assert f.name == "River Clan"
        assert f.color == "#00AAFF"


class TestStructureDef:
    def test_structure(self):
        """A structure with costs and properties."""
        s = StructureDef(
            name="workbench",
            costs={"wood": 10, "stone": 5},
            health=50,
            passable=True,
        )
        assert s.health == 50
        assert s.passable is True
        assert s.costs["wood"] == 10

    def test_impassable_structure(self):
        """A wall that blocks passage."""
        s = StructureDef(
            name="wall",
            costs={"wood": 5, "stone": 10},
            health=300,
            passable=False,
        )
        assert s.passable is False
        assert s.health == 300

    def test_shelter_protection_default(self):
        """StructureDef defaults shelter_protection to 0.0."""
        s = StructureDef(
            name="workbench",
            costs={"wood": 10, "stone": 5},
            health=50,
            passable=True,
        )
        assert s.shelter_protection == 0.0

    def test_shelter_protection_house(self):
        """House has full shelter protection."""
        s = StructureDef(
            name="house",
            costs={"wood": 15, "stone": 8, "fiber": 5},
            health=200,
            passable=True,
            shelter_protection=1.0,
        )
        assert s.shelter_protection == 1.0


class TestActionDef:
    def test_action_with_multipliers(self):
        """An action with tool multipliers."""
        a = ActionDef(
            action_type="chop",
            emoji="🪓",
            tool_multipliers=[{"item": "stone_axe", "multiplier": 0.75}],
        )
        assert a.action_type == "chop"
        assert a.emoji == "🪓"
        assert a.tool_multipliers[0]["multiplier"] == 0.75

    def test_action_no_multipliers(self):
        """An action with no tool multipliers."""
        a = ActionDef(
            action_type="eat",
            emoji="🍎",
            tool_multipliers=[],
        )
        assert a.tool_multipliers == []


class TestSkillDef:
    def test_valid_skill(self):
        """A valid skill definition."""
        s = SkillDef(
            name="combat",
            category="combat",
            base_xp_per_action={"attack": 20},
            effects_per_level={"damage_multiplier": 1.10},
        )
        assert s.name == "combat"
        assert s.category == "combat"
        assert s.base_xp_per_action == {"attack": 20}
        assert s.effects_per_level == {"damage_multiplier": 1.10}
        assert s.unlocks == []

    def test_skill_with_unlocks(self):
        """A skill with recipe unlocks."""
        s = SkillDef(
            name="crafting",
            category="crafting",
            base_xp_per_action={"craft": 8},
            effects_per_level={"speed_multiplier": 0.95, "quality_multiplier": 1.10},
            unlocks=["iron_sword", "iron_axe"],
        )
        assert len(s.unlocks) == 2
        assert "iron_sword" in s.unlocks


class TestStatusEffectDef:
    def test_valid_effect(self):
        """A valid status effect definition."""
        e = StatusEffectDef(
            name="poisoned",
            category="debuff",
            duration=60,
            max_stacks=3,
            modifiers={"health_delta": -0.5},
            triggers={"on_consume": "poisonous_berry"},
            removal_conditions=["rest_complete", "heal_action"],
        )
        assert e.name == "poisoned"
        assert e.category == "debuff"
        assert e.duration == 60
        assert e.max_stacks == 3
        assert e.modifiers["health_delta"] == -0.5

    def test_effect_defaults(self):
        """Effect with minimal fields uses sensible defaults."""
        e = StatusEffectDef(
            name="exhausted",
            category="debuff",
            duration=30,
        )
        assert e.max_stacks == 1
        assert e.modifiers == {}
        assert e.triggers == {}
        assert e.removal_conditions == []


class TestWeatherDef:
    """RED: WeatherDef model tests."""

    def test_valid_weather_def(self):
        """A valid weather definition with all fields."""
        w = WeatherDef(
            name="rainy",
            icon="🌧️",
            category="precipitation",
            duration_min=50,
            duration_max=200,
            visibility_multiplier=0.7,
            resource_regen_multiplier=1.2,
            effects={"speed_multiplier": 0.8},
            status_effects_to_apply=["wet"],
            emotion_triggers={"on_weather_rain": 0.2},
            transitions={"storm": 30, "clear": 20},
        )
        assert w.name == "rainy"
        assert w.category == "precipitation"
        assert w.duration_min == 50
        assert w.duration_max == 200
        assert w.visibility_multiplier == 0.7
        assert w.status_effects_to_apply == ["wet"]
        assert w.transitions == {"storm": 30, "clear": 20}

    def test_weather_def_defaults(self):
        """Weather def with only required fields uses defaults."""
        w = WeatherDef(name="clear", category="fair")
        assert w.duration_min == 50
        assert w.duration_max == 200
        assert w.visibility_multiplier == 1.0
        assert w.resource_regen_multiplier == 1.0
        assert w.effects == {}
        assert w.status_effects_to_apply == []
        assert w.emotion_triggers == {}
        assert w.transitions == {}


class TestTimeConfig:
    """RED: TimeConfig model tests."""

    def test_valid_time_config(self):
        """A valid TimeConfig with day/night balanced."""
        tc = TimeConfig(day_length_ticks=1000, daylight_ticks=600, night_ticks=400)
        assert tc.day_length_ticks == 1000
        assert tc.daylight_ticks == 600
        assert tc.night_ticks == 400

    def test_time_config_defaults(self):
        """TimeConfig uses sensible defaults."""
        tc = TimeConfig()
        assert tc.day_length_ticks == 1000
        assert tc.daylight_ticks == 600
        assert tc.night_ticks == 400
        assert tc.daylight_ticks + tc.night_ticks == tc.day_length_ticks

    def test_time_config_night_plus_daylight_equals_day_length(self):
        """Validator ensures daylight_ticks + night_ticks == day_length_ticks."""
        with pytest.raises(ValidationError):
            TimeConfig(day_length_ticks=1000, daylight_ticks=500, night_ticks=300)


class TestSimulationConfig:
    def test_full_config(self):
        """Full simulation config with all fields."""
        c = SimulationConfig(
            hunger_decay=0.04,
            thirst_decay=0.06,
            energy_decay=0.03,
            critical_hunger=70,
            critical_thirst=70,
            critical_llm_trigger=85,
            interaction_radius=3.0,
            reproduction_cooldown=500,
            max_population=20,
            interaction_threshold=5,
            decay_interval=100,
            combat={
                "guard_multiplier": 0.5,
                "melee_strength_factor": 0.2,
                "melee_armor_factor": 0.5,
                "ranged_intelligence_factor": 0.1,
                "ranged_armor_factor": 0.3,
            },
        )
        assert c.hunger_decay == 0.04
        assert c.max_population == 20
        assert c.combat["guard_multiplier"] == 0.5

    def test_defaults(self):
        """Config with only required fields uses defaults."""
        c = SimulationConfig()
        assert c.hunger_decay == 0.04  # default
        assert c.max_population == 20  # default
        assert c.interaction_radius == 3.0  # default


class TestAgentDefaults:
    def test_single_agent(self):
        """A single agent default entry."""
        ad = AgentDefault(
            id="agent_001",
            name="Zog",
            position=[5.0, 5.0],
            role="gatherer",
            strength=60,
            intelligence=40,
            sociability=50,
            speed=55,
            sex="male",
            age=0,
            max_age=3500,
        )
        assert ad.name == "Zog"
        assert ad.strength == 60
        assert ad.position == [5.0, 5.0]

    def test_agent_defaults_container(self):
        """Container with multiple agents."""
        ad = AgentDefaults(
            agents=[
                AgentDefault(
                    id="agent_001", name="Zog", position=[5.0, 5.0], role="gatherer",
                    strength=60, intelligence=40, sociability=50, speed=55, sex="male",
                ),
                AgentDefault(
                    id="agent_002", name="Mila", position=[35.0, 30.0], role="builder",
                    strength=70, intelligence=55, sociability=40, speed=35, sex="female",
                ),
            ]
        )
        assert len(ad.agents) == 2
        assert ad.agents[1].name == "Mila"


class TestDefinitionContainer:
    """Cross-reference validation tests."""

    def test_empty_container(self):
        """An empty container is valid (no cross-refs to check)."""
        c = DefinitionContainer()
        assert len(c.resources) == 0

    def test_valid_container(self):
        """A container with valid cross-references passes validation."""
        c = DefinitionContainer(
            resources={
                "wood": ResourceDef(name="wood", category="natural", properties={}),
                "stone": ResourceDef(name="stone", category="natural", properties={}),
                "stone_axe": ResourceDef(name="stone_axe", category="crafted", properties={}),
            },
            recipes={
                "stone_axe": RecipeDef(
                    name="stone_axe",
                    inputs={"wood": 3, "stone": 2},
                    output={"stone_axe": 1},
                    duration=10,
                    category="tool",
                ),
            },
        )
        # Validation should pass — all recipe inputs/outputs reference valid resources
        assert c.recipes["stone_axe"].duration == 10

    def test_invalid_recipe_input(self):
        """A recipe referencing an unknown resource should fail validation."""
        with pytest.raises(ValidationError):
            DefinitionContainer(
                resources={
                    "wood": ResourceDef(name="wood", category="natural", properties={}),
                },
                recipes={
                    "spear": RecipeDef(
                        name="spear",
                        inputs={"wood": 4, "stone": 3},  # "stone" is not in resources
                        output={"spear": 1},
                        duration=15,
                        category="weapon",
                    ),
                },
            )

    def test_invalid_recipe_output(self):
        """A recipe output referencing an unknown resource should fail."""
        with pytest.raises(ValidationError):
            DefinitionContainer(
                resources={
                    "wood": ResourceDef(name="wood", category="natural", properties={}),
                },
                recipes={
                    "spear": RecipeDef(
                        name="spear",
                        inputs={"wood": 4},
                        output={"spear": 1},  # "spear" is not in resources
                        duration=15,
                        category="weapon",
                    ),
                },
            )

    def test_weapon_not_required_in_resources(self):
        """Weapon/armor names like 'fist' and 'none' are equipment states,
        not inventory items — they are NOT validated against resources."""
        c = DefinitionContainer(
            resources={},
            weapons={
                "fist": WeaponDef(name="fist", damage=5, type="melee", ranged=False, ammo=None),
            },
        )
        assert c.weapons["fist"].damage == 5

    def test_container_with_weather(self):
        """DefinitionContainer can hold weather definitions."""
        c = DefinitionContainer(
            weather={
                "clear": WeatherDef(name="clear", icon="☀️", category="fair"),
                "rainy": WeatherDef(
                    name="rainy", icon="🌧️", category="precipitation",
                    status_effects_to_apply=["wet"],
                ),
            },
        )
        assert len(c.weather) == 2
        assert c.weather["clear"].category == "fair"
        assert c.weather["rainy"].status_effects_to_apply == ["wet"]

    def test_container_with_time_config(self):
        """DefinitionContainer holds time_config with validation."""
        c = DefinitionContainer(
            time_config=TimeConfig(day_length_ticks=1000, daylight_ticks=600, night_ticks=400),
        )
        assert c.time_config.day_length_ticks == 1000
        assert c.time_config.daylight_ticks == 600

    def test_container_time_config_validation(self):
        """Container validator rejects invalid time_config."""
        with pytest.raises(ValidationError):
            DefinitionContainer(
                time_config=TimeConfig(day_length_ticks=1000, daylight_ticks=500, night_ticks=300),
            )


# ===========================================================================
# Task 1.2: Loader Tests
# ===========================================================================


class TestLoadDefinitions:
    """Tests for the definitions loader."""

    def test_load_all_yamls(self):
        """Loading all YAMLs should return a DefinitionContainer with all domains."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        assert isinstance(container, DefinitionContainer)
        assert len(container.resources) > 0, "Should have resources"
        assert len(container.recipes) > 0, "Should have recipes"
        assert len(container.roles) > 0, "Should have roles"
        assert len(container.weapons) > 0, "Should have weapons"
        assert len(container.armor) > 0, "Should have armor"
        assert len(container.structures) > 0, "Should have structures"
        assert len(container.actions) > 0, "Should have actions"
        assert len(container.factions) > 0, "Should have factions"
        assert container.simulation is not None, "Should have simulation config"
        assert len(container.agent_defaults.agents) > 0, "Should have agent defaults"
        assert len(container.skills) > 0, "Should have skills"
        assert len(container.status_effects) > 0, "Should have status effects"

    def test_loaded_skill_names(self):
        """Verify specific skills exist in the loaded definitions."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        skill_names = set(container.skills.keys())
        expected = {"carpentry", "combat", "survival", "crafting", "social", "exploration", "mining", "farming"}
        assert expected.issubset(skill_names), f"Missing skills: {expected - skill_names}"

    def test_loaded_status_effect_names(self):
        """Verify specific status effects exist."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        effect_names = set(container.status_effects.keys())
        expected = {"poisoned", "exhausted", "well_fed", "hydrated", "inspired", "bleeding", "guarding", "berserk"}
        assert expected.issubset(effect_names), f"Missing effects: {expected - effect_names}"

    def test_loaded_weather_types(self):
        """Weather definitions should be loaded."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        assert len(container.weather) > 0, "Should have weather definitions"
        assert "clear" in container.weather, "clear weather should exist"

    def test_loaded_time_config(self):
        """TimeConfig should be loaded from simulation.yaml."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        assert container.time_config is not None
        assert container.time_config.day_length_ticks == 1000
        assert container.time_config.daylight_ticks == 600
        assert container.time_config.night_ticks == 400

    def test_loaded_wet_status_effect(self):
        """Wet status effect should be loaded."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        assert "wet" in container.status_effects

    def test_loaded_chilled_status_effect(self):
        """Chilled status effect should be loaded."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        assert "chilled" in container.status_effects

    def test_loaded_overheated_status_effect(self):
        """Overheated status effect should be loaded."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        assert "overheated" in container.status_effects

    def test_loaded_weather_emotion_triggers(self):
        """Emotions should have weather trigger events."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        happy = container.emotions.get("happy")
        assert happy is not None
        assert "on_weather_clear" in happy.triggers

    def test_loaded_resource_names(self):
        """Verify specific resources exist in the loaded definitions."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        resource_names = {r.name for r in container.resources.values()}
        for name in ["wood", "stone", "berries", "water"]:
            assert name in resource_names, f"{name} should be in resources"

    def test_invalid_yaml_raises(self, tmp_path: Path):
        """Loading malformed YAML should raise an error."""
        from app.core.definitions import _load_single_yaml

        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("{invalid: yaml: unquoted: # ? }")
        with pytest.raises(yaml.YAMLError):
            _load_single_yaml(bad_file)

    def test_missing_file_raises(self):
        """Reading a nonexistent file should raise FileNotFoundError."""
        from app.core.definitions import _load_single_yaml

        with pytest.raises(FileNotFoundError):
            _load_single_yaml(Path("/nonexistent/path.yaml"))


# ===========================================================================
# Task 2.x: YAML Content Comparison Tests
# ===========================================================================


class TestResourcesYAML:
    """Compare resources.yaml against world.py values."""

    def test_natural_resources_present(self):
        """All natural resource types from the simulation should be present."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        names = {r.name for r in container.resources.values()}
        expected = {"wood", "water", "berries", "stone", "iron_ore", "clay", "sand", "fiber"}
        assert expected.issubset(names), f"Missing: {expected - names}"

    def test_animals_present(self):
        """All animal types from world.py should be present."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        names = {r.name for r in container.resources.values()}
        expected = {"deer", "rabbit", "boar"}
        assert expected.issubset(names), f"Missing animals: {expected - names}"

    def test_crafted_items_present(self):
        """All crafted items should be present."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        names = {r.name for r in container.resources.values()}
        expected = {
            "stone_axe", "stone_pickaxe", "spear", "fishing_rod", "bow",
            "fiber_armor", "hoe", "iron_sword", "iron_axe", "hide_armor",
            "arrows", "planks", "stone_blade", "rope", "hide_vest",
            "iron_ingot", "bone_armor", "arrow", "workbench",
        }
        missing = expected - names
        assert not missing, f"Missing crafted items: {missing}"

    def test_deer_properties(self):
        """Deer should have correct generation params."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        deer = container.resources["deer"]
        assert deer.category == "animal"
        assert deer.properties["count"] == 10
        assert deer.properties["min_amount"] == 1
        assert deer.properties["max_amount"] == 3


class TestRecipesYAML:
    """Compare recipes.yaml against crafting.RECIPES."""

    @staticmethod
    def _expected_recipe_count() -> int:
        """Return the expected recipe count from crafting.RECIPES."""
        from app.simulation.crafting import RECIPES
        return len(RECIPES)

    def test_recipe_count_matches(self):
        """The number of recipes must match crafting.RECIPES."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        assert len(container.recipes) == self._expected_recipe_count()

    def test_stone_axe_recipe_matches(self):
        """Values for stone_axe recipe must match."""
        from app.core.definitions import load_definitions
        from app.simulation.crafting import RECIPES
        container = load_definitions()
        yaml_recipe = container.recipes["stone_axe"]
        py_recipe = RECIPES["stone_axe"]
        assert yaml_recipe.inputs == dict(py_recipe.inputs)
        assert yaml_recipe.output == dict(py_recipe.output)
        assert yaml_recipe.duration == py_recipe.duration
        assert yaml_recipe.category == py_recipe.category

    def test_all_recipes_values_match(self):
        """Every recipe's core values must match crafting.RECIPES."""
        from app.core.definitions import load_definitions
        from app.simulation.crafting import RECIPES
        container = load_definitions()
        for name, py_recipe in RECIPES.items():
            yaml_recipe = container.recipes.get(name)
            assert yaml_recipe is not None, f"Recipe {name} missing from YAML"
            assert yaml_recipe.inputs == dict(py_recipe.inputs), f"{name} inputs mismatch"
            assert yaml_recipe.output == dict(py_recipe.output), f"{name} output mismatch"
            assert yaml_recipe.duration == py_recipe.duration, f"{name} duration mismatch"
            assert yaml_recipe.category == py_recipe.category, f"{name} category mismatch"
            assert yaml_recipe.workbench == py_recipe.workbench, f"{name} workbench mismatch"
            assert yaml_recipe.modifiers == (py_recipe.modifiers or {}), f"{name} modifiers mismatch"


class TestWeaponsYAML:
    """Compare weapons.yaml against combat.WEAPONS."""

    def test_weapon_count_matches(self):
        from app.core.definitions import load_definitions
        from app.simulation.combat import WEAPONS
        container = load_definitions()
        assert len(container.weapons) == len(WEAPONS)

    def test_all_weapon_values_match(self):
        from app.core.definitions import load_definitions
        from app.simulation.combat import WEAPONS
        container = load_definitions()
        for name, py_weapon in WEAPONS.items():
            y_w = container.weapons.get(name)
            assert y_w is not None, f"Weapon {name} missing"
            assert y_w.damage == py_weapon["damage"], f"{name} damage"
            assert y_w.type == py_weapon["type"], f"{name} type"
            assert y_w.ranged == py_weapon["ranged"], f"{name} ranged"
            assert y_w.ammo == py_weapon.get("ammo"), f"{name} ammo"
            if py_weapon.get("max_range") is not None:
                assert y_w.max_range == py_weapon["max_range"], f"{name} max_range"


class TestArmorYAML:
    """Compare armor.yaml against combat.ARMOR."""

    def test_armor_count_matches(self):
        from app.core.definitions import load_definitions
        from app.simulation.combat import ARMOR
        container = load_definitions()
        assert len(container.armor) == len(ARMOR)

    def test_all_armor_values_match(self):
        from app.core.definitions import load_definitions
        from app.simulation.combat import ARMOR
        container = load_definitions()
        for name, py_armor in ARMOR.items():
            y_a = container.armor.get(name)
            assert y_a is not None, f"Armor {name} missing"
            assert y_a.damage_reduction == py_armor["damage_reduction"], f"{name} damage_reduction"


class TestRolesYAML:
    """Compare roles.yaml against DEFINITIONS.roles (which is the same data)."""

    def test_role_count_matches(self):
        from app.core.definitions import load_definitions, DEFINITIONS
        container = load_definitions()
        assert len(container.roles) == len(DEFINITIONS.roles)
        assert container.default_role == DEFINITIONS.default_role

    def test_all_role_values_match(self):
        from app.core.definitions import load_definitions, DEFINITIONS
        container = load_definitions()
        for name, py_role in DEFINITIONS.roles.items():
            y_r = container.roles.get(name)
            assert y_r is not None, f"Role {name} missing"
            assert y_r.allowed_actions == py_role.allowed_actions, f"{name} allowed_actions"
            assert y_r.stat_modifiers == py_role.stat_modifiers, f"{name} stat_modifiers"
            assert y_r.tool_allowlist == py_role.tool_allowlist, f"{name} tool_allowlist"
            assert y_r.priorities == py_role.priorities, f"{name} priorities"


class TestStructuresYAML:
    """Compare structures.yaml against STRUCTURE_COSTS + STRUCTURE_DEFINITIONS."""

    def test_structure_count_matches(self):
        from app.core.definitions import load_definitions
        from app.simulation.structures import STRUCTURE_COSTS
        container = load_definitions()
        assert len(container.structures) == len(STRUCTURE_COSTS)

    def test_all_structure_values_match(self):
        from app.core.definitions import load_definitions
        from app.simulation.structures import STRUCTURE_COSTS, STRUCTURE_DEFINITIONS
        container = load_definitions()
        for name, costs in STRUCTURE_COSTS.items():
            y_s = container.structures.get(name)
            assert y_s is not None, f"Structure {name} missing"
            assert y_s.costs == costs, f"{name} costs mismatch"
            props = STRUCTURE_DEFINITIONS.get(name, {})
            assert y_s.health == props.get("health", 100), f"{name} health mismatch"
            assert y_s.passable == props.get("passable", True), f"{name} passable mismatch"


class TestFactionsYAML:
    """Compare factions.yaml against faction.py _create_defaults values."""

    def test_faction_count_matches(self):
        from app.core.definitions import load_definitions
        container = load_definitions()
        # _create_defaults creates 3 factions
        assert len(container.factions) == 3

    def test_faction_names_and_colors(self):
        from app.core.definitions import load_definitions
        container = load_definitions()
        expected = {
            "River Clan": "#00AAFF",
            "Stone Hold": "#FF8800",
            "Green Ward": "#44BB44",
        }
        for name, color in expected.items():
            f = container.factions.get(name)
            assert f is not None, f"Faction {name} missing"
            assert f.color == color, f"{name} color mismatch"


class TestSimulationYAML:
    """Compare simulation.yaml values against engine.py constants."""

    def test_simulation_constants_match(self):
        from app.core.definitions import load_definitions
        from app.simulation import engine as eng
        container = load_definitions()
        cfg = container.simulation
        assert cfg.hunger_decay == eng.HUNGER_DECAY
        assert cfg.thirst_decay == eng.THIRST_DECAY
        assert cfg.energy_decay == eng.ENERGY_DECAY
        assert cfg.critical_hunger == eng.CRITICAL_HUNGER
        assert cfg.critical_thirst == eng.CRITICAL_THIRST
        assert cfg.critical_llm_trigger == eng.CRITICAL_LLM_TRIGGER
        assert cfg.interaction_radius == eng.INTERACTION_RADIUS
        assert cfg.reproduction_cooldown == eng.REPRODUCTION_COOLDOWN
        assert cfg.max_population == eng.MAX_POPULATION
        assert cfg.interaction_threshold == eng.INTERACTION_THRESHOLD
        assert cfg.decay_interval == eng.DECAY_INTERVAL

    def test_combat_params(self):
        """Combat parameters match CombatManager formulas."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        combat = container.simulation.combat
        # guard_multiplier from calculate_damage_with_guard (damage *= 0.5)
        assert combat["guard_multiplier"] == 0.5
        # melee_strength_factor from calculate_melee_damage (attacker_strength * 0.2)
        assert combat["melee_strength_factor"] == 0.2
        # melee_armor_factor from calculate_melee_damage (defender_armor * 0.5)
        assert combat["melee_armor_factor"] == 0.5
        # ranged_intelligence_factor from calculate_ranged_damage (attacker_intelligence * 0.1)
        assert combat["ranged_intelligence_factor"] == 0.1
        # ranged_armor_factor from calculate_ranged_damage (defender_armor * 0.3)
        assert combat["ranged_armor_factor"] == 0.3


class TestAgentDefaultsYAML:
    """Compare agent_defaults.yaml against AgentFactory.create_default_agents."""

    def test_agent_count_matches(self):
        from app.core.definitions import load_definitions
        from app.simulation.agent import AgentFactory
        container = load_definitions()
        py_agents = AgentFactory.create_default_agents()
        assert len(container.agent_defaults.agents) == len(py_agents)

    def test_zog_values_match(self):
        from app.core.definitions import load_definitions
        container = load_definitions()
        zog = container.agent_defaults.agents[0]
        assert zog.name == "Zog"
        assert zog.position == [5.0, 5.0]
        assert zog.role == "gatherer"
        assert zog.strength == 60
        assert zog.intelligence == 40
        assert zog.sex == "male"
        assert zog.max_age == 3500

    def test_mila_values_match(self):
        from app.core.definitions import load_definitions
        container = load_definitions()
        mila = container.agent_defaults.agents[1]
        assert mila.name == "Mila"
        assert mila.position == [35.0, 30.0]
        assert mila.role == "builder"
        assert mila.strength == 70
        assert mila.intelligence == 55
        assert mila.sociability == 40
        assert mila.speed == 35
        assert mila.sex == "female"

    def test_kael_values_match(self):
        from app.core.definitions import load_definitions
        container = load_definitions()
        kael = container.agent_defaults.agents[2]
        assert kael.name == "Kael"
        assert kael.position == [45.0, 10.0]
        assert kael.role == "scout"
        assert kael.strength == 45
        assert kael.intelligence == 60
        assert kael.speed == 80


class TestActionsYAML:
    """Compare actions.yaml against actions.py values."""

    def test_chop_action_multipliers(self):
        """Chop action should have stone_axe and iron_axe multipliers."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        chop = container.actions.get("chop")
        assert chop is not None, "chop action missing"
        mults = {(m["item"], m["multiplier"]) for m in chop.tool_multipliers}
        assert ("stone_axe", 0.75) in mults, "stone_axe/chop multiplier missing"
        assert ("iron_axe", 0.5) in mults, "iron_axe/chop multiplier missing"

    def test_mine_action_multiplier(self):
        """Mine action should have stone_pickaxe multiplier."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        mine = container.actions.get("mine")
        assert mine is not None, "mine action missing"
        mults = {(m["item"], m["multiplier"]) for m in mine.tool_multipliers}
        assert ("stone_pickaxe", 0.75) in mults

    def test_farm_action_multiplier(self):
        """Farm action should have hoe multiplier."""
        from app.core.definitions import load_definitions
        container = load_definitions()
        farm = container.actions.get("farm")
        assert farm is not None, "farm action missing"
        mults = {(m["item"], m["multiplier"]) for m in farm.tool_multipliers}
        assert ("hoe", 0.5) in mults

    def test_emoji_for_each_action(self):
        """Every action type should have an emoji."""
        from app.core.definitions import load_definitions
        from app.simulation.actions import ActionType, ACTION_EMOJIS
        container = load_definitions()
        for action_type in ActionType:
            name = action_type.value
            y_action = container.actions.get(name)
            assert y_action is not None, f"Action {name} missing from YAML"
            expected_emoji = ACTION_EMOJIS[action_type]
            assert y_action.emoji == expected_emoji, f"{name} emoji mismatch"
