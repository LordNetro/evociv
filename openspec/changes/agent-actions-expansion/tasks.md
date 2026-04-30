# Tasks: Agent Actions Expansion

**Test count target**: +75 new tests across all phases
**Files to create**: 4 new modules + 1 config file = 5 files
**Files to modify**: 8 existing files

## Phase 1 — Foundation (6 tasks)

- [x] **P1-T1**: Create `backend/config/roles.py` with ROLES dict (10 roles: gatherer/hunter/fisher/farmer/miner/builder/crafter/scout/fighter/healer), each with priorities, allowed_actions, stat_modifiers, tool_allowlist; DEFAULT_ROLE="gatherer". Deps: none. Tests: role dict has all 10 entries, correct keys per role.
- [x] **P1-T2**: Create `backend/app/simulation/roles.py` with lookup, apply_role_stats(), role_allows_action(). Deps: P1-T1. Tests: stat mods applied on creation, unknown role raises, default gatherer fallback, action restriction blocks disallowed ActionTypes.
- [x] **P1-T3**: Set HUNGER_DECAY=0.04, THIRST_DECAY=0.06, ENERGY_DECAY=0.03 in engine.py. Deps: none. Tests: hunger+0.4/thirst+0.6/energy-0.3 over 10 ticks.
- [x] **P1-T4**: Add MINE/EXPLORE to ActionType enum + REGISTRY handlers + ACTION_EMOJIS + get_action_duration(). MINE yields ore from mineral tiles, EXPLORE pathfinds to nearest undiscovered tile. Deps: none. Tests: MINE on iron yields ore, no-mineral failure, EXPLORE boundary handling.
- [x] **P1-T5**: Add IRON/CLAY/SAND/FIBER to ResourceType enum in world.py; update generate_initial_resources() with new tile counts/amounts/regen rates. Deps: none. Tests: new resources appear at correct densities, regeneration works per type.
- [x] **P1-T6**: Refactor engine._fsm_evaluate() to iterate ROLES[agent.role].priorities before hardcoded chain; fallback to survival chain when no match. Deps: P1-T1, P1-T2. Tests: gatherer produces same output as old chain, fighter prioritizes ATTACK over GATHER, scout picks EXPLORE.

## Phase 2 — Crafting + Tools (4 tasks)

- [x] **P2-T1**: Create `backend/app/simulation/crafting.py` with Recipe dataclass, RECIPES dict (≥10 recipes from spec), CraftingManager.craft() with full validation (ingredients, tools, station, skills). Deps: P1-T5 (resources). Tests: successful plank craft, missing ingredient, missing tool, missing forge station, atomic rollback, tool modifier reduces duration.
- [x] **P2-T2**: Add CRAFT/HUNT/FISH to ActionType + handlers. CRAFT delegates to CraftingManager. HUNT requires weapon≠fist, consumes arrow if bow. FISH requires tool equipped. Deps: P2-T1. Tests: hunt with bow yields meat+hide, hunt with fist fails, fish with spear yields fish, fish without tool fails.
- [x] **P2-T3**: Add animal tile resource type to world.py (deer/rabbit/boar) spawning on empty grass; flee behavior: move 1 tile away when agent ≤3 tiles; depletable amount (1-3). Deps: none. Tests: animal generation, flee on proximity, amount decreases with HUNT.
- [x] **P2-T4**: Add apply_tool_modifier() helper in actions.py; modify get_action_duration() to reduce duration based on equipped tool quality (stone_axe 0.75x, iron_axe 0.5x). Deps: P2-T1. Tests: stone_axe reduces CHOP duration, iron_axe reduces more, no tool = base duration.

## Phase 3 — Structures (4 tasks)

- [x] **P3-T1**: Create `backend/app/simulation/structures.py` with Structure dataclass (id/type/position/owner/health/properties), StructureManager (add/remove/get/list), structure definitions with resource costs (storage_hut/house/forge/farm/wall). Deps: none. Tests: CRUD operations, get_by_position, get_by_owner.
- [x] **P3-T2**: Add BUILD/FARM to ActionType + handlers. BUILD consumes resources, validates adjacent empty tile, places Structure. FARM yields 3 berries after 5-tick duration at farm structure. Deps: P3-T1. Tests: build succeeds with resources, fails with insufficient, fails on occupied tile, farm without structure fails.
- [x] **P3-T3**: Add World.structures: dict[tuple,int], Structure; update is_passable() to return False for wall-type; structure-avoiding BFS in find_path(). Deps: P3-T1. Tests: wall blocks path at (5,5), non-wall structures are passable, path routed around wall.
- [x] **P3-T4**: Add farm auto-generation (2 berries/tick into owner inventory when owner ≤1 tile from farm); add house rest bonus (energy+20 instead of +10 when on house tile); storage_hut doubles stack limit within 3 tiles. Deps: P3-T2. Tests: farm generates within range, no yield outside range, house boosts rest, storage expansion.

## Phase 4 — Combat (5 tasks)

- [x] **P4-T1**: Create `backend/app/simulation/combat.py` with CombatManager, damage formula (melee: weapon_dmg+str*0.2-armor-str*0.1, ranged: weapon_dmg+int*0.1-armor), weapon/armor stat tables (fist/spear/bow/iron_sword etc). Deps: none. Tests: melee calc with spear vs hide_vest, ranged calc with bow, guard 0.5x mitigation, min=1 clamp.
- [x] **P4-T2**: Add ATTACK/GUARD/HEAL to ActionType + handlers. ATTACK validates adjacency/range, ammo for bow. GUARD sets is_guarding flag. HEAL consumes 1 berry, heals 10+int*0.1. Deps: P4-T1. Tests: melee attack damages target, ranged out-of-range error, no ammo error, guard halves damage, self-attack blocked, HEAL restores health.
- [x] **P4-T3**: Add equipment field to Agent: equipment: dict[str,str] = {"weapon":"fist","armor":"none","tool":"none"}. Deps: none. Tests: defaults on new agent, custom values settable via factory.
- [x] **P4-T4**: Add combat interruption in _run_agent_fsm(): compare health before/after each tick cycle; if decreased, force FSM to evaluate (transition from idle/moving/executing). Deps: P4-T2. Tests: executing agent re-evaluates after taking damage, guards can retaliate.
- [x] **P4-T5**: Add cause="violence" death path in _process_needs(); emit combat_death SimEvent with attacker_id and target_id in metadata; update relationships (attacker→target score -0.5). Deps: P4-T2. Tests: combat death removes agent, emits combat_death event, relationship penalty applied.

## Phase 5 — LLM + Polish (6 tasks)

- [x] **P5-T1**: Add equipment field to AgentState schema + _build_agent_state() snapshot method. Deps: P4-T3. Tests: equipment serialized in snapshot JSON with correct defaults.
- [x] **P5-T2**: Add StructureUpdate Pydantic schema + structures field to WorldSnapshot; add dirty_structures tracking to WorldSnapshotBuilder. Deps: P3-T1, P3-T3. Tests: structures appear in full and delta snapshots.
- [x] **P5-T3**: Update JSON_FORMAT_INSTRUCTION in prompts.py with all 10 new actions in steps.action enum; add role description + behavioral guidance (from ROLES) to build_agent_prompt(). Deps: P1-T1. Tests: new actions present in format instruction, role context rendered for hunter/fighter.
- [x] **P5-T4**: Add nearby structures context section to STATE_PROMPT_TEMPLATE; populate via world.get_nearby_structures(). Deps: P3-T3. Tests: structures listed in prompt when agent is near them.
- [x] **P5-T5**: Add "craft"/"build"/"fight"/"combat_death" event types and "violence" death cause to event_queue.py SimEvent docstring + create_death_event(). Deps: P4-T5. Tests: new event types pushable and drainable.
- [x] **P5-T6**: Update `backend/app/simulation/__init__.py` exports (roles/crafting/structures/combat modules); balance pass on rates/durations/damage/energy costs; comprehensive integration tests: role-differentiated sim, craft→tool→CHOP faster loop, BUILD→wall blocks BFS, combat→death flow, MINE→CRAFT→iron_sword→ATTACK pipeline.
