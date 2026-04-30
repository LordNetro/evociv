# Proposal: Agent Actions Expansion

## Intent

Agents spend ~80% ticks on survival (eat/drink/gather). Roles are inert strings. No crafting, buildings, or combat. This change makes roles drive behavior, adds 10 actions for economy/crafting/combat, and slows rates so agents have time for non-survival work.

## Scope

**In**: Rate rebalance (hunger 0.04, thirst 0.06, energy 0.03). Data-driven role priorities + per-role actions. 10 new actions (MINE, HUNT, FISH, FARM, CRAFT, BUILD, ATTACK, GUARD, EXPLORE, HEAL). Crafting (recipes, tools, workbenches). Structures (storage, forge, farm, walls, house). Combat (damage, weapons, armor, violent death). Role-differentiated FSM. Tests.

**Out**: Full LLM rewrite, ChromaDB memory, multi-tile buildings, faction roles, weather, RL.

## Capabilities

**New**: `agent-roles` (definitions + priorities), `crafting-system` (recipes + tools + CRAFT), `structures` (buildings + placement + functions), `combat-system` (damage + weapons + armor), `resources-extended` (mining/hunting/fishing/farming).

**Modified**: `simulation-engine` (role-driven FSM, rates, combat phase), `agent-society` (new ActionTypes, equipment, behavioral roles).

## Approach

Five independent phases: 1) Rates → roles → generic FSM → MINE/EXPLORE → prompt context. 2) crafting.py + recipes.json → CRAFT → tool modifiers → HUNT/FISH. 3) structures.py → BUILD → world layer → FARM. 4) combat.py → ATTACK/GUARD → weapons/armor → violent death. 5) Prompt polish → balance pass → comprehensive tests → snapshot fields.

## Affected Areas

| Area | Impact | What |
|------|--------|------|
| `roles.py`, `crafting.py`, `structures.py`, `combat.py` | New | 4 modules + `config/recipes.json` |
| `actions.py`, `agent.py`, `engine.py`, `world.py` | Modified | +10 types, role FSM, structures, resources |
| `snapshot.py`, `prompts.py`, `schemas.py` | Modified | New fields serialized |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Role FSM breaks existing behavior | Low | Default "gatherer" preserves old priority chain |
| Combat kills agents too fast | Med | Low initial damage; balance in Phase 5 |
| Structures break pathfinding | Med | BFS handles obstacles; passable flag on struct |

## Rollback Plan

Revert 7 modified files. Delete 4 new modules + recipes.json. In-memory only — no DB.

## Dependencies

All phases depend on `simulation-engine`. Phase 3 depends on Phase 1 (BUILD). Phase 4 depends on Phase 2 (weapons needed).

## Success Criteria

- [ ] Roles produce different behavioral priorities in same sim
- [ ] All 10 new actions execute without errors
- [ ] Agents spend <50% ticks on survival (rebalanced rates)
- [ ] Crafted tools modify outcomes (stone axe → faster CHOP)
- [ ] Structures block pathfinding on grid
- [ ] Combat reduces HP; weapons boost; armor mitigates
- [ ] All existing tests pass; new tests cover every new system
