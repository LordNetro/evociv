# Archive Report: agent-actions-expansion

**Change**: agent-actions-expansion
**Archived**: 2026-04-30
**Status**: Complete — all 25 tasks, all 7 critical fixes, verification PASS (292/292)
**Mode**: Hybrid (openspec filesystem + Engram persistence)

---

## Summary

This change expanded the EVOCIV agent simulation from its original 10 actions and single hardcoded FSM priority ordering into a full data-driven system with:

- **10 agent roles** with distinct priority tables, allowed actions, and stat modifiers
- **10 new ActionTypes** (MINE, HUNT, FISH, FARM, CRAFT, BUILD, ATTACK, GUARD, EXPLORE, HEAL)
- **Crafting system** with 7 recipes, tool modifiers, and atomic rollback
- **Structure system** (wall, storage_hut, house, forge, farm) with pathfinding, capacity bonuses, rest recovery, and auto-generation
- **Combat system** with melee/ranged damage formulas, weapons, armor, guard mitigation, and death mechanics
- **Resource expansion** with 4 new resources (iron, clay, sand, fiber) and animal tiles (deer, rabbit, boar)
- **Rebalanced decay rates** (0.04/0.06/0.03) to give agents breathing room
- **LLM prompt enrichment** with role guidance, equipment context, threat assessment, craftable recipes, and nearby structures
- **Schema extensions** for equipment and structures in snapshots

### Key Numbers

| Metric | Value |
|--------|-------|
| Tasks | 25/25 complete |
| Tests | 292 passing (0 failed, 0 skipped) |
| New files created | 10 |
| Files modified | 12 |
| Spec scenarios | 82/82 compliant |
| Post-verify critical fixes | 7/7 resolved |

---

## Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| architecture (simulation-engine) | Updated | Added 7 new requirements (R11-R17): decay rates, role-driven FSM, new actions, combat interruption, structure-aware pathfinding, FSM transitions, action durations |
| agent-society | Updated | Modified F7 (colony stats extended with structures/equipment); added 6 new features (F9-F14): new ActionTypes, equipment fields, role-specific prompts, structure awareness in prompts, Equipment in AgentState, Structures in WorldSnapshot |

### New Spec Files Created

| File | Purpose |
|------|---------|
| `openspec/specs/agent-roles/spec.md` | Role definitions, priority tables, allowed actions, stat modifiers |
| `openspec/specs/crafting-system/spec.md` | Recipe registry, CRAFT action, tool modifiers, atomic crafting |
| `openspec/specs/structures/spec.md` | Structure dataclass, StructureManager, BUILD/FARM actions, structure types |
| `openspec/specs/combat-system/spec.md` | Combat formulas, weapon/armor types, GUARD mitigation, death mechanics |
| `openspec/specs/resources-extended/spec.md` | Extended resource types, world generation, animal tiles, regeneration |

### Delta Spec Files

| File | Action |
|------|--------|
| `openspec/changes/agent-actions-expansion/specs/simulation-engine/spec.md` | Merged into `openspec/specs/architecture/spec.md` |
| `openspec/changes/agent-actions-expansion/specs/agent-society/spec.md` | Merged into `openspec/specs/agent-society/spec.md` |

---

## Implementation Artifacts

### Files Created

| File | Purpose |
|------|---------|
| `backend/config/roles.py` | ROLES dict with all 10 role definitions |
| `backend/config/__init__.py` | Config package init |
| `backend/app/simulation/roles.py` | Role helper functions (apply_role_stats, role_allows_action) |
| `backend/app/simulation/crafting.py` | Recipe dataclass, RECIPES dict, CraftingManager |
| `backend/app/simulation/structures.py` | Structure dataclass, StructureManager (CRUD + queries) |
| `backend/app/simulation/combat.py` | CombatManager with damage formulas, weapon/armor stat tables |
| `backend/tests/test_roles.py` | 31 tests for role system |
| `backend/tests/test_crafting.py` | 26 tests for crafting system |
| `backend/tests/test_structures.py` | 19 tests for structure system |
| `backend/tests/test_combat.py` | 6 tests for combat formulas |

### Files Modified

| File | Changes |
|------|---------|
| `backend/app/simulation/actions.py` | Added 10 new action handlers; tool modifiers; inventory capacity |
| `backend/app/simulation/agent.py` | Added role_data, equipment, _storage_nearby fields; factory applies role stats |
| `backend/app/simulation/engine.py` | Rebalanced decay rates; role-driven FSM; combat interruption; structure-aware pathfinding; storage flag |
| `backend/app/simulation/world.py` | Added new resources, animal tiles, regeneration logic |
| `backend/app/simulation/snapshot.py` | Added equipment to AgentState; structures to WorldSnapshot |
| `backend/app/simulation/event_queue.py` | Added combat event types |
| `backend/app/simulation/__init__.py` | Updated exports |
| `backend/app/ai/prompts.py` | Role guidance, equipment, threat assessment, craftable recipes, nearby structures in prompts |
| `backend/app/ai/orchestrator.py` | Computes craftable recipes, equipment string, nearby hostiles |
| `backend/app/models/schemas.py` | Added equipment to AgentState; structures to WorldSnapshot |
| `backend/tests/test_engine.py` | Added integration tests for all new systems |
| `backend/tests/test_ai.py` | Added LLM prompt enrichment tests |

---

## Feature Coverage

| Feature | Requirements | Scenarios | Test Count | Status |
|---------|-------------|-----------|------------|--------|
| Agent Roles | R1-R8 | 6 | 31 | ✅ COMPLIANT |
| Crafting System | R1-R8 | 13 | 26 | ✅ COMPLIANT |
| Structures | R1-R14 | 14 | 19 | ✅ COMPLIANT |
| Combat System | R1-R14 | 25 | 6 + engine | ✅ COMPLIANT |
| Resources Extended | R1-R11 | 10 | engine tests | ✅ COMPLIANT |
| Agent-Society Delta | F9-F14 | 10 | 39 | ✅ COMPLIANT |
| Simulation-Engine Delta | R11-R17 | 7 | engine tests | ✅ COMPLIANT |

---

## Deviations from Design

| Design Decision | Actual | Assessment |
|----------------|--------|------------|
| `equipped_weapon`/`equipped_armor`/`experience` fields | `equipment: dict[str, str]` with keys `weapon`, `armor`, `tool` | Valid improvement — more extensible |
| `blocks_movement: bool` on Structure | Checks `structure_type == "wall"` in `is_passable()` | Functionally equivalent |

No design regressions. All spec requirements satisfied.

---

## Verification

- **Tests**: 292/292 passing (pytest, Python 3.13)
- **Spec Compliance**: 82/82 scenarios compliant (100%)
- **TDD Compliance**: 6/6 checks passed
- **Critical Issues**: 0 remaining (all 7 resolved)
- **Warnings**: 0
- **Suggestions**: 5 (unused import, f-string, pytest-cov, mypy, HUNT weapon check)

### Final Verdict

**PASS** — Ready for archive. The change is complete, verified, and stable.

---

## Artifact Store State

| Artifact | Location | Status |
|----------|----------|--------|
| Proposal | `openspec/changes/agent-actions-expansion/proposal.md` | ✅ In place |
| Design | `openspec/changes/agent-actions-expansion/design.md` | ✅ In place |
| Tasks | `openspec/changes/agent-actions-expansion/tasks.md` | ✅ In place |
| Verify Report | `openspec/changes/agent-actions-expansion/verify-report.md` | ✅ In place |
| Archive Report | `openspec/changes/agent-actions-expansion/archive-report.md` | ✅ This file |
| Delta Specs | `openspec/changes/agent-actions-expansion/specs/` | ✅ In place |
| Apply Progress | Engram `sdd/agent-actions-expansion/apply-progress` | ✅ Saved |
| Archive Report | Engram `sdd/agent-actions-expansion/archive-report` | ✅ Saved |

---

## SDD Cycle Complete

The change has been fully planned, implemented, verified, and archived.
Ready for the next change.
