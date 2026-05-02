# Proposal: Data-Driven Definitions

## Intent

Move ALL hardcoded game data from Python modules into YAML configs under `configs/definitions/`. Code becomes pure engine — enables modding, runtime inspection, and tuning without touching Python.

## Scope

### In Scope
- 10 YAML files under `configs/definitions/` covering all 7 data domains
- Pydantic-validated loader (`app/core/definitions.py` + `definition_models.py`)
- Delete `config/roles.py` (→ `roles.yaml`)
- Phase-1 comparison tests asserting YAML == old data
- Migrate consumers: crafting, combat, structures, actions, roles, world, agent, engine, faction
- Add `pyyaml` to `requirements.txt`

### Out of Scope
- Hot-reload or runtime YAML watching
- Per-world config overrides (stay in `configs/example-world-*/`)
- Refactoring engine logic — data moves only
- Frontend changes

## Capabilities

None — pure refactor, no spec-level behavior changes.

## Approach

**Phase 1 — Infrastructure**: Pydantic models + YAML loader with cross-ref validation. Load once at import, fail-fast.

**Phase 2 — Comparison tests**: Assert YAML-loaded data == old Python dicts before any migration.

**Phase 3 — Migration** (7 tracks, parallelizable): Replace hardcoded dicts with `load_definitions()`. Each module keeps `__all__` exports.

**Phase 4 — Cleanup**: Remove `config/roles.py`, `create_default_agents()`, `_create_defaults()`.

## Affected Areas

| Path | Change |
|------|--------|
| `configs/definitions/*.yaml` (10) | NEW — definition files |
| `backend/app/core/definitions.py` | NEW — YAML loader |
| `backend/app/core/definition_models.py` | NEW — Pydantic models |
| `backend/config/roles.py` | DELETE — replaced by YAML |
| `backend/app/simulation/crafting.py` | MOD — RECIPES → YAML |
| `backend/app/simulation/combat.py` | MOD — WEAPONS/ARMOR → YAML |
| `backend/app/simulation/structures.py` | MOD — costs/defs → YAML |
| `backend/app/simulation/actions.py` | MOD — modifiers/emojis → YAML |
| `backend/app/simulation/roles.py` | MOD — import from YAML |
| `backend/app/simulation/world.py` | MOD — resource params → YAML |
| `backend/app/simulation/agent.py` | MOD — defaults → YAML |
| `backend/app/simulation/engine.py` | MOD — constants → YAML |
| `backend/app/simulation/faction.py` | MOD — defaults → YAML |
| `backend/requirements.txt` | MOD — add pyyaml |
| `backend/tests/test_definitions.py` | NEW — comparison tests |
| All other sim modules + tests | MOD — update imports |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| YAML value mismatch breaks sim | Med | Comparison tests assert exact equality pre-migration |
| Cross-ref misses edge case | Low | Pydantic + explicit checks in loader |
| Import-order issue at startup | Low | Lazy-loaded cache on first `load_definitions()` call |

## Rollback Plan

`git checkout -- backend/ configs/`, remove `pyyaml`, run tests.

## Success Criteria

- [ ] All 7 domains load from YAML with IDENTICAL data to old dicts
- [ ] Full test suite passes (114 existing + new tests)
- [ ] Zero hardcoded game data remains in `backend/app/simulation/` or `backend/config/`
