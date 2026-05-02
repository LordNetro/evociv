# Design: Data-Driven Definitions

## Technical Approach

Pydantic + PyYAML validated loader. Module-level frozen `DefinitionContainer` singleton populated at first import. Code becomes pure engine — no hardcoded data. Comparison tests assert YAML == old dicts before any consumer migration.

## Architecture Decisions

| Decision | Options | Chosen | Rationale |
|----------|---------|--------|-----------|
| Loader trigger | Lazy on first call / eager on import | Eager (import-time) | Fail-fast at startup. Acceptable since configs are small (200 lines total). |
| Singleton shape | Module dict / Frozen dataclass | Frozen `DefinitionContainer` dataclass | Type-safe access (`DEFINITIONS.resources`), immutable after load, IDE autocomplete. |
| ResourceType enum | Keep enum / String-only | Keep enum, populate values from YAML | Enum type safety across `world.py` grid, `_place_resource()`, tile checks. YAML string values validated against enum. |
| ITEM_MODIFIERS | Keep as separate dict / Derive from recipes | DERIVE from recipes `post_init` | Eliminates duplication. `get_item_modifiers()` reads recipes' `.modifiers` at runtime. |
| Engine decay constants | Move to YAML / Keep in `engine.py` | Keep in `engine.py` | These are simulation tuning params with formulas, not game data. Decoupled from definition system. |
| Action emojis | Move to YAML / Keep in code | Keep in `ACTION_EMOJIS` dict | Emojis are frontend display metadata, not game data. No benefit from YAML. |
| Duration formulas | Move to YAML / Keep as Python | Keep as `get_action_duration()` Python | Formulas depend on `agent.speed/strength/energy` — cannot be expressed as static YAML. |
| Faction default names | Move to YAML / Keep code | Move to YAML as defaults list | These are game content (clan names/colors), pure data. |
| Agent default templates | Keep `create_default_agents()` / Move to YAML | Move to YAML as agent defaults | Zog/Mila/Kael are content, not engine logic. |
| Circular imports | Load anywhere / Dedicated core module | `app.core.definitions` imports ONLY pydantic + yaml | Zero risk. `definitions.py` never imports from `app.simulation.*`. |

## Data Flow

```
configs/definitions/*.yaml
        │
        ▼
app.core.definition_models.py  ← Pydantic models with validators
        │
        ▼
app.core.definitions.py        ← load_definitions() + DEFINITIONS singleton
        │
        ├──► app.simulation.recipes   → was RECIPES dict
        ├──► app.simulation.combat    → was WEAPONS/ARMOR
        ├──► app.simulation.structures → was STRUCTURE_COSTS/DEFINITIONS
        ├──► app.simulation.actions   → ITEM_MODIFIERS derived from recipes
        ├──► app.simulation.roles     → was config.roles.ROLES
        ├──► app.simulation.world     → generate_initial_resources params
        ├──► app.simulation.agent     → create_default_agents templates
        ├──► app.simulation.faction   → _create_defaults() names/colors
        └──► app.ai.prompts            → _get_craftable_recipes()
```

## YAML Schemas (10 files)

Each file maps 1:1 to current Python data structures:

| File | Domain | Keys |
|------|--------|------|
| `resources.yaml` | Resource generation params | `trees`, `water`, `berries`, `stone`, `iron_ore`, `clay`, `sand`, `fiber`, `deer`, `rabbit`, `boar` — each with `count`, `amount_min`, `amount_max`, `regen_rate` |
| `recipes.yaml` | 18 crafting recipes | Flat list under `recipes:` key, each with `name`, `inputs`, `output`, `workbench` (optional), `duration`, `category`, `modifiers` (optional) |
| `weapons.yaml` | 4 weapon definitions | Flat list under `weapons:` key, each with `name`, `damage`, `type`, `ranged`, `ammo` (optional), `max_range` (optional) |
| `armor.yaml` | 3 armor definitions | Flat list under `armor:` key, each with `name`, `damage_reduction` |
| `structures.yaml` | 6 structure definitions | Flat list under `structures:` key, each with `name`, `costs`, `health`, `passable` |
| `roles.yaml` | 10 role definitions | Replaces `config/roles.py`. Flat list under `roles:` key, each with `name`, `priorities`, `allowed_actions`, `stat_modifiers`, `tool_allowlist` |
| `actions.yaml` | Tool speed multipliers | `tool_duration_multipliers` as list of `{item, action, multiplier}` tuples. No emojis — keep in code. |
| `factions.yaml` | Default faction templates | `defaults` list with `name` and `color` |
| `agents.yaml` | Default agent templates | `defaults` list with `name`, `role`, `position`, `attributes`, `equipment` |
| `simulation.yaml` | Simulation constants | `interaction_radius`, `reproduction_cooldown`, `max_population`, `interaction_threshold`, `decay_interval`, `critical_hunger`, `critical_thirst`, `critical_llm_trigger` |

**Key structural rule**: Every YAML file uses a top-level key (plural noun) wrapping a list. This keeps YAML human-readable and allows easy extension:

```yaml
# recipes.yaml example
recipes:
  - name: stone_axe
    inputs: {wood: 3, stone: 2}
    output: {stone_axe: 1}
    duration: 10
    category: tool
    modifiers: {chop_speed: 2, attack_damage: 5}
  - name: workbench_structure
    inputs: {wood: 10, stone: 5}
    output: {workbench: 1}
    duration: 20
    category: structure
```

## Pydantic Model Hierarchy

```
DefinitionContainer (frozen)
├── resources: list[ResourceDef]
├── recipes: dict[str, RecipeDef]        # keyed by name
├── weapons: dict[str, WeaponDef]        # keyed by name
├── armor: dict[str, ArmorDef]           # keyed by name
├── structures: dict[str, StructureDef]  # keyed by name
├── roles: dict[str, RoleDef]            # keyed by name
├── tool_duration_multipliers: list[tuple[str, str, float]]
├── factions: list[FactionDef]
├── agent_defaults: list[AgentDefaults]
├── simulation: SimulationConfig
```

Cross-reference validators in Pydantic:
- RecipeDef inputs → must be known resources or items
- RecipeDef workbench → must be a known structure type
- RecipeDef output keys → must exist as items
- WeaponDef ammo → must be a known item
- RoleDef priorities action names → must be valid ActionType values
- Tool duration item names → must be known recipes

## Migration Plan

### Module-by-module

1. **`app/core/definition_models.py`** — NEW. All Pydantic models with validators.
2. **`app/core/definitions.py`** — NEW. `_resolve_path()` → `_load_yaml()` → Pydantic validate → compose `DefinitionContainer`. Functions: `load_definitions()` (idempotent cache), `get_definitions()`.
3. **`requirements.txt`** — MOD. Add `pyyaml>=6.0`.
4. **Phase-2 comparison tests**: `test_definitions.py` loads YAML and compares values against old dicts. These guard migration.
5. **Migrate consumers** — each module replaces its hardcoded dict with `DEFINITIONS.<domain>`:
   - `crafting.py`: `RECIPES` → `DEFINITIONS.recipes`
   - `combat.py`: `WEAPONS` → `DEFINITIONS.weapons`, `ARMOR` → `DEFINITIONS.armor`
   - `structures.py`: `STRUCTURE_COSTS` + `STRUCTURE_DEFINITIONS` → `DEFINITIONS.structures`
   - `actions.py`: Remove `ITEM_MODIFIERS` — `get_item_modifiers()` derives from `DEFINITIONS.recipes`
   - `roles.py`: `ROLES` import → `DEFINITIONS.roles`
   - `world.py`: `generate_initial_resources()` params → `DEFINITIONS.resources`
   - `agent.py`: `create_default_agents()` → `DEFINITIONS.agent_defaults`
   - `engine.py`: Critical thresholds + interaction constants → `DEFINITIONS.simulation`
   - `faction.py`: `_create_defaults()` → `DEFINITIONS.factions`
   - `ai/prompts.py`: `_get_craftable_recipes()` reads from `DEFINITIONS.recipes`
6. **Cleanup**: Delete `config/roles.py`, `config/__init__.py` (if empty).
7. **Test update**: Update existing tests to import from new sources, keeping assertions identical.

### Backward compatibility

Each module keeps its public symbol exports (`__all__`) but the values now reference `DEFINITIONS.<domain>`. Consumers that `from app.simulation.crafting import RECIPES` still work — `RECIPES` is a module-level alias.

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Validation | Pydantic model integrity | Unit test per model: verify field types, required fields, default values |
| Cross-ref | Recipe inputs exist as items | Pydantic validator test: supply bad ref → assert `ValidationError` |
| Comparison | YAML == old Python dicts | `test_definitions.py` — load YAML, compare every value to old dicts |
| Migration | Each module still works | Existing tests remain unchanged (same public API) |
| Edge case | Missing YAML file | `test_definitions.py` — verify `FileNotFoundError` with clear message |
| Edge case | Malformed YAML | Verify `yaml.YAMLError` wrapped in descriptive exception |

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| YAML float precision mismatch | Medium | Use `pytest.approx()` in comparison tests |
| YAML None vs missing key | Low | Pydantic `Optional` fields with `Field(default=None)` |
| Merge conflict on `requirements.txt` | Low | Standard, easy to resolve |
| Forgot to update a consumer | Low | Comparison tests catch value mismatches pre-migration |
| YAML boolean vs string | Low | Pydantic `bool` / `str` validation catches at load time |
