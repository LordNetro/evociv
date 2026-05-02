"""Game definitions loader — reads YAML configs and validates via Pydantic.

This module is the SINGLE entry point for all game data.
It MUST NOT import any simulation modules (``app.simulation.*``) to
prevent circular imports — simulation modules may import this module.

Usage::

    from app.core.definitions import DEFINITIONS
    DEFINITIONS.recipes["stone_axe"].duration  # 10
    DEFINITIONS.resources["wood"].properties["regen_rate"]  # 0.01
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.core.definition_models import (
    ActionDef,
    AgentDefaults,
    ArmorDef,
    DefinitionContainer,
    EmotionDef,
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

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DEFINITIONS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "configs" / "definitions"

# Ordered list of (filename, container_key, model_type) for deterministic loading
_YAML_FILES: list[tuple[str, str, type]] = [
    ("resources.yaml", "resources", ResourceDef),
    ("recipes.yaml", "recipes", RecipeDef),
    ("weapons.yaml", "weapons", WeaponDef),
    ("armor.yaml", "armor", ArmorDef),
    ("structures.yaml", "structures", StructureDef),
    ("actions.yaml", "actions", ActionDef),
    ("roles.yaml", "roles", RoleDef),
    ("factions.yaml", "factions", FactionDef),
    ("simulation.yaml", "simulation", SimulationConfig),
    ("agent_defaults.yaml", "agent_defaults", AgentDefaults),
    ("skills.yaml", "skills", SkillDef),
    ("status_effects.yaml", "status_effects", StatusEffectDef),
    ("emotions.yaml", "emotions", EmotionDef),
    ("weather.yaml", "weather", WeatherDef),
]


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _load_single_yaml(path: Path) -> Any:
    """Read and parse a single YAML file.

    Raises:
        FileNotFoundError: if *path* does not exist.
        yaml.YAMLError: if the file contains invalid YAML.
    """
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_definitions(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert raw YAML dicts into Pydantic model instances grouped by container key.

    Handles the different structures of each YAML file:
    - resources: dict of name → ResourceDef
    - recipes: dict of name → RecipeDef
    - weapons: dict of name → WeaponDef
    - armor: dict of name → ArmorDef
    - structures: dict of name → StructureDef
    - actions: dict of name → ActionDef
    - roles: dict of name → RoleDef (with extra top-level default_role)
    - factions: dict of name → FactionDef
    - simulation: single SimulationConfig
    - agent_defaults: single AgentDefaults
    """
    result: dict[str, Any] = {}

    # ── resources ──
    resources_raw = raw.get("resources", {})
    result["resources"] = {
        name: ResourceDef(**data) for name, data in resources_raw.items()
    }

    # ── recipes ──
    recipes_raw = raw.get("recipes", {})
    result["recipes"] = {
        name: RecipeDef(**data) for name, data in recipes_raw.items()
    }

    # ── weapons ──
    weapons_raw = raw.get("weapons", {})
    result["weapons"] = {
        name: WeaponDef(**data) for name, data in weapons_raw.items()
    }

    # ── armor ──
    armor_raw = raw.get("armor", {})
    result["armor"] = {
        name: ArmorDef(**data) for name, data in armor_raw.items()
    }

    # ── structures ──
    structures_raw = raw.get("structures", {})
    result["structures"] = {
        name: StructureDef(**data) for name, data in structures_raw.items()
    }

    # ── actions ──
    actions_raw = raw.get("actions", {})
    result["actions"] = {
        name: ActionDef(**data) for name, data in actions_raw.items()
    }

    # ── roles (with default_role) ──
    roles_raw = raw.get("roles", {})
    result["roles"] = {
        name: RoleDef(**data) for name, data in roles_raw.items()
    }
    result["default_role"] = raw.get("default_role", "gatherer")

    # ── factions ──
    factions_raw = raw.get("factions", {})
    result["factions"] = {
        name: FactionDef(**data) for name, data in factions_raw.items()
    }

    # ── simulation ──
    simulation_raw = raw.get("simulation", {})
    result["simulation"] = SimulationConfig(**simulation_raw) if simulation_raw else SimulationConfig()

    # Extract time config from simulation yaml (from the 'time' key inside simulation block)
    time_raw = simulation_raw.get("time", {}) if simulation_raw else {}
    result["time_config"] = TimeConfig(**time_raw) if time_raw else TimeConfig()

    # ── agent_defaults ──
    agent_defaults_raw = raw.get("agent_defaults", {})
    result["agent_defaults"] = AgentDefaults(**agent_defaults_raw) if agent_defaults_raw else AgentDefaults()

    # ── skills ──
    skills_raw = raw.get("skills", {})
    result["skills"] = {
        name: SkillDef(name=name, **data) for name, data in skills_raw.items()
    }

    # ── status_effects ──
    status_effects_raw = raw.get("status_effects", {})
    result["status_effects"] = {
        name: StatusEffectDef(name=name, **data) for name, data in status_effects_raw.items()
    }

    # ── emotions ──
    emotions_raw = raw.get("emotions", {})
    result["emotions"] = {
        name: EmotionDef(name=name, **data) for name, data in emotions_raw.items()
    }

    # ── weather ──
    weather_raw = raw.get("weather", {})
    result["weather"] = {
        name: WeatherDef(
            name=name,
            **{k: v for k, v in data.items() if k != "name"},
        )
        for name, data in weather_raw.items()
    }

    return result


def _load_all_yamls(definitions_dir: Path | None = None) -> dict[str, Any]:
    """Load all YAML files from *definitions_dir* and merge into a single dict.

    Each file's top-level key is included.  Later files override earlier ones for
    the same key (no collisions expected — each file has a unique top-level key).
    """
    base_dir = definitions_dir or _DEFINITIONS_DIR
    merged: dict[str, Any] = {}
    for filename, _container_key, _model_type in _YAML_FILES:
        path = base_dir / filename
        data = _load_single_yaml(path)
        if data is not None:
            merged.update(data)
    return merged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_definitions(definitions_dir: Path | None = None) -> DefinitionContainer:
    """Load ALL YAML definition files, validate, and return a frozen container.

    Args:
        definitions_dir: Optional override for the definitions directory.
                         Defaults to ``configs/definitions/`` relative to project root.

    Returns:
        A frozen ``DefinitionContainer`` with cross-references validated.

    Raises:
        FileNotFoundError: if any YAML file is missing.
        yaml.YAMLError: if any YAML file is malformed.
        pydantic.ValidationError: if data fails model validation or cross-ref checks.
    """
    raw = _load_all_yamls(definitions_dir)
    built = _build_definitions(raw)
    return DefinitionContainer(**built)


# ── Eagerly-loaded frozen singleton ──

DEFINITIONS: DefinitionContainer = load_definitions()
"""Module-level singleton.  Import this from simulation modules to access all game data.

Example::

    from app.core.definitions import DEFINITIONS
    recipe = DEFINITIONS.recipes["stone_axe"]
    print(recipe.duration)  # 10
"""
