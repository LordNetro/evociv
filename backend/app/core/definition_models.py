"""Pydantic models for all game definition domains.

These models validate YAML config files loaded from ``configs/definitions/``.
All cross-references (recipe inputs/outputs, weapon names, etc.) are validated
by ``DefinitionContainer`` using ``model_validator``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Domain Models
# ---------------------------------------------------------------------------


class ResourceDef(BaseModel):
    """A resource definition: natural resource, animal, crafted item, or sub-product."""

    name: str
    category: str  # "natural", "animal", "crafted", "subproduct"
    properties: dict[str, Any] = Field(default_factory=dict)


class RecipeDef(BaseModel):
    """A craftable recipe definition matching ``crafting.Recipe``."""

    name: str
    inputs: dict[str, int]
    output: dict[str, int]
    workbench: str | None = None
    workbench_level: int = 0
    duration: int = 10
    category: str = "misc"
    modifiers: dict[str, Any] = Field(default_factory=dict)


class WeaponDef(BaseModel):
    """A weapon definition matching ``combat.WEAPONS`` entries."""

    name: str
    damage: int = 5
    type: str = "melee"  # "melee" | "ranged"
    ranged: bool = False
    ammo: str | None = None
    max_range: int | None = None


class ArmorDef(BaseModel):
    """An armor definition matching ``combat.ARMOR`` entries."""

    name: str
    damage_reduction: int = 0


class StructureDef(BaseModel):
    """A buildable structure definition."""

    name: str
    costs: dict[str, int] = Field(default_factory=dict)
    health: int = 100
    passable: bool = True
    properties: dict[str, Any] = Field(default_factory=dict)
    shelter_protection: float = 0.0  # 0.0 (none) to 1.0 (full)


class ActionDef(BaseModel):
    """Metadata for an action type: emoji and tool duration multipliers."""

    action_type: str
    emoji: str
    tool_multipliers: list[dict[str, Any]] = Field(default_factory=list)


class RoleDef(BaseModel):
    """A role definition matching ``config.roles.ROLES`` entries."""

    name: str
    description: str = ""
    priorities: list[tuple[str, int]] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    stat_modifiers: dict[str, int] = Field(default_factory=dict)
    tool_allowlist: list[str] = Field(default_factory=list)
    default_equipment: dict[str, str] = Field(default_factory=dict)


class FactionDef(BaseModel):
    """A faction definition with name and display color."""

    name: str
    color: str  # hex colour, e.g. "#00AAFF"


class SkillDef(BaseModel):
    """A skill definition: category, XP per action, and per-level effects."""

    name: str
    category: str  # combat, crafting, survival, social, exploration, labor
    base_xp_per_action: dict[str, int]
    effects_per_level: dict[str, float]
    unlocks: list[str] = []


class StatusEffectDef(BaseModel):
    """A status effect template: duration, stacking, modifiers, triggers."""

    name: str
    category: str  # buff, debuff, neutral
    duration: int
    max_stacks: int = 1
    modifiers: dict[str, float] = {}
    triggers: dict[str, Any] = {}
    removal_conditions: list[str] = []


class EmotionDef(BaseModel):
    """An emotion definition: category, icon, decay, effects, triggers.

    Emotions use a float intensity model (0.0–1.0) with configurable per-tick
    decay. Trigger events add delta to intensity. Effects use strongest-wins
    aggregation (same as ``StatusEffectManager``).
    """

    name: str = ""
    category: str = "neutral"  # positive, negative, neutral
    icon: str = ""
    decay_per_tick: float = 0.005
    effects: dict[str, float] = {}
    triggers: dict[str, float] = {}


class WeatherDef(BaseModel):
    """A weather type definition with effects, transitions, and emotion triggers."""

    name: str = ""
    icon: str = ""
    category: str = "fair"  # fair, precipitation, extreme, fog
    duration_min: int = 50
    duration_max: int = 200
    visibility_multiplier: float = 1.0
    resource_regen_multiplier: float = 1.0
    effects: dict[str, float] = Field(default_factory=dict)
    status_effects_to_apply: list[str] = Field(default_factory=list)
    emotion_triggers: dict[str, float] = Field(default_factory=dict)
    transitions: dict[str, int] = Field(default_factory=dict)


class NightEffects(BaseModel):
    """Night-time effects on various agent stats."""

    resource_regen_multiplier: float = 1.0
    thirst_decay_multiplier: float = 1.0
    energy_regen_multiplier: float = 1.0
    visibility_multiplier: float = 1.0


class TimeConfig(BaseModel):
    """Day/night cycle configuration with validation."""

    day_length_ticks: int = 1000
    daylight_ticks: int = 600
    night_ticks: int = 400
    effects: dict[str, NightEffects] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_day_night(self) -> TimeConfig:
        """Ensure daylight_ticks + night_ticks == day_length_ticks."""
        if self.daylight_ticks + self.night_ticks != self.day_length_ticks:
            raise ValueError(
                f"daylight_ticks ({self.daylight_ticks}) + night_ticks ({self.night_ticks}) "
                f"must equal day_length_ticks ({self.day_length_ticks})"
            )
        return self


class SimulationConfig(BaseModel):
    """Simulation engine constants — decay rates, thresholds, combat factors, etc."""

    hunger_decay: float = 0.04
    thirst_decay: float = 0.06
    energy_decay: float = 0.03
    critical_hunger: int = 70
    critical_thirst: int = 70
    critical_llm_trigger: int = 85
    interaction_radius: float = 3.0
    reproduction_cooldown: int = 500
    max_population: int = 20
    interaction_threshold: int = 5
    decay_interval: int = 100
    combat: dict[str, float] = Field(default_factory=dict)


class AgentDefault(BaseModel):
    """Default agent configuration for initial population."""

    id: str = ""
    name: str
    position: list[float] = Field(default_factory=lambda: [0.0, 0.0])
    role: str = "gatherer"
    strength: int = 50
    intelligence: int = 50
    sociability: int = 50
    speed: int = 50
    sex: str = "male"
    age: int = 0
    max_age: int = 3000
    equipment: dict[str, str] = Field(
        default_factory=lambda: {"weapon": "fist", "armor": "none", "tool": "none"}
    )


class AgentDefaults(BaseModel):
    """Container for default agent configurations."""

    agents: list[AgentDefault] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Container with cross-reference validators
# ---------------------------------------------------------------------------


def _resource_names(resources: dict[str, ResourceDef]) -> set[str]:
    """Return the set of resource names known in *resources*."""
    return set(resources.keys())


class DefinitionContainer(BaseModel):
    """Frozen container holding ALL game definitions with cross-reference validation.

    Cross-reference rules enforced by ``model_validator(mode="after")``:
    - Every recipe input and output MUST reference a known resource.
    - Every weapon/armor/structure name MUST reference a known resource (if resources given).
    """

    model_config = {"frozen": True}

    resources: dict[str, ResourceDef] = Field(default_factory=dict)
    recipes: dict[str, RecipeDef] = Field(default_factory=dict)
    weapons: dict[str, WeaponDef] = Field(default_factory=dict)
    armor: dict[str, ArmorDef] = Field(default_factory=dict)
    structures: dict[str, StructureDef] = Field(default_factory=dict)
    actions: dict[str, ActionDef] = Field(default_factory=dict)
    roles: dict[str, RoleDef] = Field(default_factory=dict)
    factions: dict[str, FactionDef] = Field(default_factory=dict)
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    agent_defaults: AgentDefaults = Field(default_factory=AgentDefaults)
    default_role: str = "gatherer"
    skills: dict[str, SkillDef] = Field(default_factory=dict)
    status_effects: dict[str, StatusEffectDef] = Field(default_factory=dict)
    emotions: dict[str, EmotionDef] = Field(default_factory=dict)
    weather: dict[str, WeatherDef] = Field(default_factory=dict)
    time_config: TimeConfig = Field(default_factory=TimeConfig)

    @model_validator(mode="after")
    def _validate_cross_references(self) -> DefinitionContainer:
        """Validate that all cross-references between definitions are consistent.

        Raises ``ValueError`` (wrapped as ``ValidationError`` by Pydantic) when
        a reference points to an unknown resource.

        Rules enforced:
        - Every recipe input and output MUST reference a known resource.
        - Weapon and armor names are NOT validated against resources because
          some are equipment states (``fist``, ``none``) rather than inventory items.
        """
        known_resources = _resource_names(self.resources)

        # ── Recipes: inputs and outputs must reference known resources ──
        for rname, recipe in self.recipes.items():
            for item in recipe.inputs:
                if item not in known_resources:
                    raise ValueError(
                        f"Recipe '{rname}' input '{item}' is not in resources "
                        f"(known: {sorted(known_resources)})"
                    )
            for item in recipe.output:
                if item not in known_resources:
                    raise ValueError(
                        f"Recipe '{rname}' output '{item}' is not in resources "
                        f"(known: {sorted(known_resources)})"
                    )

        return self
