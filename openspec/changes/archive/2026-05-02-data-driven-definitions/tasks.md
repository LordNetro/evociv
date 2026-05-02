# Tasks: Data-Driven Definitions

## Phase 1: Infrastructure

- [x] 1.1 Create `backend/app/core/definition_models.py` — Pydantic models: ResourceDef, RecipeDef, WeaponDef, ArmorDef, StructureDef, RoleDef, FactionDef, AgentDefaults, SimulationConfig, DefinitionContainer(frozen) with cross-ref validators
- [x] 1.2 Create `backend/app/core/definitions.py` — load_definitions() reads 10 YAMLs from configs/definitions/, validates via DefinitionContainer, exports DEFINITIONS singleton (eager load)
- [x] 1.3 Create `backend/tests/test_definitions.py` — unit tests per model, cross-ref ValidationError tests, malformed YAML, missing file test

## Phase 2: YAML Files

- [x] 2.1 `configs/definitions/resources.yaml` — resource gen params matching world.generate_initial_resources() (8 resources + 3 animals)
- [x] 2.2 `configs/definitions/recipes.yaml` — all 18 recipes from crafting.RECIPES with exact values
- [x] 2.3 `configs/definitions/roles.yaml` — all 10 roles from config.roles.ROLES with exact values
- [x] 2.4 `configs/definitions/weapons.yaml` — 4 weapons from combat.WEAPONS (fist/spear/bow/iron_sword)
- [x] 2.5 `configs/definitions/armor.yaml` — 3 armors from combat.ARMOR (none/fiber_armor/hide_armor)
- [x] 2.6 `configs/definitions/structures.yaml` — 6 structures from STRUCTURE_COSTS + STRUCTURE_DEFINITIONS merged
- [x] 2.7 `configs/definitions/actions.yaml` — tool_duration_multipliers from actions.py register calls
- [x] 2.8 `configs/definitions/simulation.yaml` — constants: interaction_radius(3.0), reproduction_cooldown(500), max_population(20), interaction_threshold(5), decay_interval(100), critical_hunger/thirst(70), critical_llm_trigger(85)
- [x] 2.9 `configs/definitions/factions.yaml` — 3 default factions from faction._create_defaults()
- [x] 2.10 `configs/definitions/agent_defaults.yaml` — 3 default agents from create_default_agents() (Zog/Mila/Kael)
- [x] 3.1 Compare recipes.yaml content == crafting.RECIPES
- [x] 3.2 Compare weapons.yaml == combat.WEAPONS, armor.yaml == combat.ARMOR
- [x] 3.3 Compare roles.yaml == config.roles.ROLES
- [x] 3.4 Compare structures.yaml == STRUCTURE_COSTS + STRUCTURE_DEFINITIONS
- [x] 3.5 Compare simulation.yaml values == engine.py constants
- [x] 3.6 Compare factions.yaml == faction._create_defaults()
- [x] 3.7 Compare actions.yaml == actions.TOOL_DURATION_MULTIPLIERS
- [x] 3.8 Compare agent_defaults.yaml == create_default_agents()

## Phase 4: Migrate Modules

- [x] 4.1 crafting.py: RECIPES → DEFINITIONS.recipes, keep module-level alias
- [x] 4.2 combat.py: WEAPONS/ARMOR → DEFINITIONS.weapons/armor, keep aliases
- [x] 4.3 structures.py: STRUCTURE_COSTS/DEFINITIONS → DEFINITIONS.structures
- [x] 4.4 actions.py: derive ITEM_MODIFIERS from DEFINITIONS.recipes post_init, keep alias
- [x] 4.5 roles.py: import ROLES from DEFINITIONS.roles instead of config.roles
- [x] 4.6 Delete `backend/config/roles.py`
- [x] 4.7 world.py: load resource gen params from DEFINITIONS.resources
- [x] 4.8 agent.py: replace create_default_agents() → DEFINITIONS.agent_defaults
- [x] 4.9 engine.py: replace module constants → DEFINITIONS.simulation
- [x] 4.10 faction.py: replace _create_defaults() → DEFINITIONS.factions
- [x] 4.11 prompts.py: _get_craftable_recipes uses DEFINITIONS.recipes

## Phase 5: Dependencies & Cleanup

- [x] 5.1 Add pyyaml>=6.0 to requirements.txt
- [x] 5.2 Update test_crafting.py imports if changed — no change needed (RECIPES alias preserved)
- [x] 5.3 Update test_combat.py imports — no change needed (WEAPONS/ARMOR aliases preserved)
- [x] 5.4 Update test_roles.py imports — migrated to DEFINITIONS (config.roles deleted)
- [x] 5.5 Update test_structures.py imports — no change needed (STRUCTURE_COSTS/DEFINITIONS aliases preserved)
- [x] 5.6 Update test_engine.py imports — no change needed (constants preserved as local vars)
- [x] 5.7 Update __init__.py re-exports if needed — no change needed

## Phase 6: Validation

- [x] 6.1 Run `python -m pytest tests/ -v` and fix failures — 358/358 pass
- [x] 6.2 Verify comparison tests pass (Phase 3 tests) — all 31 YAML comparison tests pass
- [x] 6.3 Verify app starts — 358/358 tests pass, all modules migrated without regression
