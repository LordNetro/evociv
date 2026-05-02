# Design: Skill Progression + Status Effects

## Technical Approach

Two new Manager classes following the established pattern (CombatManager, CraftingManager, FactionManager). **SkillManager** (pure static methods, no instance state) and **StatusEffectManager** (same pattern). Both load definitions from YAML via `DEFINITIONS`, operate on Agent dataclass fields, and integrate into the existing `_tick()` → `_run_agent_fsm()` pipeline.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Inline in engine.py vs dedicated modules | Inline is simpler short-term but violates separation; engine.py is already 1444 lines | **Dedicated modules**: `skills.py` + `status_effects.py` |
| Instance-based vs static-only Manager | Instance fits FactionManager; CombatManager uses static; crafting uses mixed | **Pure static** on both (no state = testable without engine) |
| Store XP total or only level | Total XP enables future XP-per-level display; level-only saves memory | **Store level only** (`dict[str, int]`) — matches spec S2, XP is per-call computed |
| Effect storage as dict of dicts vs typed class | Typed dataclass better DX but adds import complexity | **dict of dicts** — matches pattern used by `last_action_result: Optional[Any]` |

## Data Flow

```
_tick()
  ├─ 1. _process_needs()
  ├─ 1.5 [NEW] StatusEffectManager.process_tick(agent)    ← ticks effects, expires
  ├─ 2. _run_agent_fsm(agent)
  │    ├─ executing: handler() → [NEW] SkillManager.award_xp()
  │    └─ llm_waiting: [NEW] poison fallback check
  ├─ ...
  └─ snapshot._build_agent_state(): includes skills + effects
```

See spec for full ASCII sequence diagrams.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/simulation/skills.py` | Create | `SkillManager` — XP award, speed/combat/crafting modifiers |
| `backend/app/simulation/status_effects.py` | Create | `StatusEffectManager` — apply, tick, expire, aggregate modifiers |
| `configs/definitions/skills.yaml` | Create | 8 skill definitions with base_xp_per_action, effects_per_level |
| `configs/definitions/status_effects.yaml` | Create | 7 status effect definitions with modifiers, triggers |
| `backend/app/simulation/agent.py` | Modify | Add `skills: dict[str, int]`, `active_effects: dict[str, dict]` to Agent |
| `backend/app/simulation/actions.py` | Modify | `get_action_duration()`: skill + effect modifiers; `handle_eat()`: poison trigger |
| `backend/app/simulation/engine.py` | Modify | `_tick()`: process_tick call; `_fsm_executing()`: award_xp post-hook; `_fsm_llm_waiting()`: poison fallback |
| `backend/app/simulation/combat.py` | Modify | `calculate_melee_damage()`: add skill + effect modifiers |
| `backend/app/core/definition_models.py` | Modify | Add `SkillDef`, `StatusEffectDef`; update `DefinitionContainer` |
| `backend/app/core/definitions.py` | Modify | Add `_YAML_FILES` entries for skills.yaml, status_effects.yaml; add `_build_definitions()` sections |
| `backend/app/models/schemas.py` | Modify | Add `skills`, `active_effects` fields to `AgentState` |
| `backend/app/simulation/snapshot.py` | Modify | `_build_agent_state()`: include skills + active_effects |
| `backend/app/ai/prompts.py` | Modify | `STATE_PROMPT_TEMPLATE`: add Skills line, Effects line |
| `backend/app/ai/prompts.py` | Modify | `build_agent_prompt()`: format skills + effects, pass to template |
| `backend/tests/test_skills.py` | Create | XP award, level-up, modifiers, zero-skill baseline |
| `backend/tests/test_status_effects.py` | Create | Apply, tick, expire, stacking, modifiers, poison trigger |
| `backend/tests/test_combat.py` | Modify | Update damage formulas for skill/effect modifiers |
| `backend/tests/test_actions.py` | Modify | Duration tests with skill + effect modifiers |

## Interfaces / Contracts

### SkillManager (static)
```python
class SkillManager:
    @staticmethod
    def award_xp(agent: Agent, action_type: ActionType) -> None: ...
    @staticmethod
    def get_speed_modifier(agent: Agent, skill_name: str) -> float: ...
    @staticmethod
    def get_combat_modifier(agent: Agent, skill_name: str) -> float: ...
    @staticmethod
    def get_crafting_quality(agent: Agent, skill_name: str) -> float: ...
```

- `(1 - 0.05 * level)` for speed, floor at 0.5
- `(1 + 0.1 * level)` for combat damage
- XP thresholds: `[0, 100, 250, 500, 1000, 2000, 4000, ...]`
- Level-up emits `event_queue.push("skill_up", severity="warning")`

### StatusEffectManager (static)
```python
class StatusEffectManager:
    @staticmethod
    def apply(agent: Agent, effect_name: str, source: str | None = None) -> None: ...
    @staticmethod
    def process_tick(agent: Agent) -> None: ...
    @staticmethod
    def get_total_modifiers(agent: Agent) -> dict[str, float]: ...
    @staticmethod
    def has_effect(agent: Agent, effect_name: str) -> bool: ...
    @staticmethod
    def remove_effect(agent: Agent, effect_name: str) -> None: ...
    @staticmethod
    def clear_all(agent: Agent) -> None: ...
```

### YAML: skills.yaml (8 skills)
- carpentry: category=crafting, xp={chop:5, build:8}, effects={speed_mult:0.05}
- combat: category=combat, xp={attack:20, guard:10}, effects={damage_mult:0.1}
- survival: category=survival, xp={gather:3, hunt:8, fish:6}, effects={speed_mult:0.05}
- crafting: category=crafting, xp={craft:10}, effects={quality_mult:0.1, speed_mult:0.05}
- social: category=social, xp={talk:5, trade:5}, effects={speed_mult:0.05}
- exploration: category=exploration, xp={explore:4, move:2}, effects={speed_mult:0.05}
- mining: category=survival, xp={mine:7}, effects={speed_mult:0.05}
- farming: category=survival, xp={farm:6}, effects={speed_mult:0.05}

### YAML: status_effects.yaml (7 effects)
- poisoned: category=debuff, duration=20, max_stacks=3, modifiers={health:-2}, triggers={on_tick:damage}
- exhausted: category=debuff, duration=30, max_stacks=1, modifiers={speed:0.5}
- well_fed: category=buff, duration=40, max_stacks=1, modifiers={speed:1.1}
- hydrated: category=buff, duration=40, max_stacks=1, modifiers={speed:1.1}
- inspired: category=buff, duration=50, max_stacks=1, modifiers={speed:1.2, damage:1.2}
- bleeding: category=debuff, duration=15, max_stacks=2, modifiers={health:-3}, triggers={on_tick:damage}
- guarding: category=buff, duration=5, max_stacks=1, modifiers={defense:1.5}
- berserk: category=buff, duration=10, max_stacks=1, modifiers={damage:2.0, defense:0.5}

## Integration Design (per file)

### `agent.py` — Agent dataclass
```python
# Add two fields:
skills: dict[str, int] = field(default_factory=dict)
active_effects: dict[str, dict] = field(default_factory=dict)
```
AgentFactory already initializes with default args — no factory change needed.

### `actions.py` — get_action_duration()
```python
# After apply_tool_modifier, add:
skill_mod = SkillManager.get_speed_modifier(agent, _skill_for_action(action_type))
effect_mod = StatusEffectManager.get_total_modifiers(agent).get("speed", 1.0)
return max(1, round(base * skill_mod * effect_mod))
# Helper _skill_for_action maps ActionType → skill name
```
Handle poison in `handle_eat()`: after consuming berries, check tile `hidden_properties.is_poisonous`.

### `engine.py` — _tick()
```python
# After step 1 (_process_needs), before step 2 (FSM):
for agent in self.agents:
    StatusEffectManager.process_tick(agent)
```
In `_fsm_executing()`: after handler returns `result.success`, call `SkillManager.award_xp(agent, action_type)`.
In `_fsm_llm_waiting()`: add poison instinct check before existing hunger instinct.

### `combat.py` — calculate_melee_damage()
```python
# After existing formula, multiply by skill + effect modifiers:
skill_mod = SkillManager.get_combat_modifier(attacker, "combat")
effect_mod = StatusEffectManager.get_total_modifiers(attacker).get("damage", 1.0)
return max(1.0, base * skill_mod * effect_mod)
```
Note: `attacker` here is an `Agent` instance. Current signature takes `attacker_strength: float` — we'll need to change to accept an `Agent` or add a new method.

### `prompts.py` — STATE_PROMPT_TEMPLATE
```python
# Add after Inventory line:
{skills_line}

# Add after Equipment line:
{effects_line}
```
Format helpers serialize `agent.skills` to `"Skills: carpentry:5, combat:3, ..."` and active effects to `"Effects: poisoned(35t), well_fed(20t)"`.

### `snapshot.py` — _build_agent_state()
```python
AgentState(
    ...
    skills=dict(agent.skills),
    active_effects={name: data["remaining_ticks"] for name, data in agent.active_effects.items()},
)
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit (skills) | XP award, level-up thresholds, modifiers, zero-skill baseline | Create Agent(minimal), call SkillManager static methods directly |
| Unit (effects) | Apply new/refresh, tick expiration, stacking rules, modifier aggregation | Create Agent, call StatusEffectManager methods directly |
| Unit (combat) | Updated damage formulas with skill + effect modifiers | Parametrize `calculate_melee_damage` with Agent mock |
| Unit (actions) | Duration formula includes skill + effect factor | Mock SkillManager/StatusEffectManager or create agents with known skills |
| Integration | Poison trigger in handle_eat, poison fallback instinct | Test through engine with full tick loop |

## Risks & Mitigations

- **Circular import**: `skills.py` imports `Agent`, `actions.py` imports `skills.py` → Agent imports DEFINITIONS (not actions). Safe: no circular path.
- **Backward compatibility**: Existing tests assume no skills/effects on Agent. Both fields default to `{}` → zero-skill = 1.0x multiplier. **All existing tests pass unchanged.**
- **Performance**: `get_total_modifiers()` iterates all effects each tick. At ~20 agents × ~2 effects avg = negligible cost. If scaling, cache with dirty flag.
- **Poison fallback correctness**: Must not override valid non-survival plans when health is above 50%. Threshold check `agent.health < 50` gates the override.

## Open Questions

None — all design decisions are scoped and documented.
