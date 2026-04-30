# Spec: combat-system

## Purpose

Define combat mechanics: damage formulas, weapons, armor, the ATTACK and GUARD actions, violent death, and combat logging. Enables agents to fight each other (and hostile structures) with ranged and melee combat.

## Dependencies

- **Depends on**: simulation-engine, crafting-system

## Capabilities

### capability: combat-system
**Depends on**: simulation-engine, crafting-system

#### Requirements

| # | Requirement | Strength |
|---|-------------|----------|
| R1 | A new `ATTACK` ActionType MUST be added. The handler receives a `target_id` (agent or structure) from the plan step. Melee attacks require the target to be on an adjacent tile (Manhattan distance ≤ 1). Ranged attacks (bow) require the target within 5 tiles and consume 1 `arrow` from inventory. | MUST |
| R2 | A new `GUARD` ActionType MUST be added. Guarding reduces incoming damage by 50% for the duration of the guard action. The guard state persists until the agent's next action completes or the agent moves. | MUST |
| R3 | Damage formula (melee): `damage = max(1, weapon_damage + (attacker.strength * 0.2) - target.armor_rating - (target.strength * 0.1))`. Minimum damage is always 1. | MUST |
| R4 | Damage formula (ranged): `damage = max(1, weapon_damage + (attacker.intelligence * 0.1) - target.armor_rating)`. No strength bonus for ranged; intelligence provides accuracy bonus. | MUST |
| R5 | Weapon types and base damage: `fist` (1, always available), `stone_axe` (3), `spear` (5), `bow` (4, ranged), `club` (4), `iron_sword` (8). Weapons MUST be equipped in the `weapon` equipment slot to be used. | MUST |
| R6 | Armor types and armor rating: `hide_vest` (2), `wood_shield` (3), `bone_armor` (4). Armor MUST be equipped in the `armor` equipment slot. Armor is NOT consumed on damage (durable). | MUST |
| R7 | The Agent dataclass MUST gain `equipment` field: `dict[str, str]` mapping slot names to item IDs. Valid slots: `weapon`, `armor`, `tool`. Default: `{"weapon": "fist", "armor": "none", "tool": "none"}`. | MUST |
| R8 | When an agent takes damage (health reduction), the agent's FSM MUST be interrupted if currently in `idle`, `moving`, or `executing` states. The interrupted agent transitions to `evaluate` and if a hostile target is within range, MAY retaliate via LLM or instinct. | MUST |
| R9 | When `agent.health <= 0` from combat damage, the agent MUST die with `cause="combat"`. The death event MUST be `type="combat_death"` with a description including the attacker's name. | MUST |
| R10 | Combat events MUST be logged as SimEvents: `type="combat"` for attacks (with damage dealt, attacker, target) and `type="combat_death"` for deaths. | MUST |
| R11 | The GUARD status MUST be tracked as a temporary flag on the agent: `is_guarding: bool` (default False). When `is_guarding=True`, all incoming damage is multiplied by 0.5 (rounded up, minimum 1). The flag clears when the guard action duration expires or the agent moves. | MUST |
| R12 | An agent MUST NOT attack itself. The ATTACK handler MUST check `target_id != agent.id` and return `success=False` if they match. | MUST |
| R13 | Weapons and armor items are craftable via the crafting system (see crafting-system/spec.md). Fist is the default unarmed weapon and requires no item. | MUST |
| R14 | The LLM prompt MUST include the agent's equipment loadout (weapon, armor, tool) and current threat assessment (nearby hostile agents, own health). | MUST |

#### Scenarios

### Scenario: Melee attack — damage calculation
- GIVEN attacker with `strength=60` wielding `spear` (damage 5), and target with `armor_rating=2` (hide_vest) and `strength=50`
- WHEN the attacker executes ATTACK on the target
- THEN damage = max(1, 5 + (60 * 0.2) - 2 - (50 * 0.1)) = max(1, 5 + 12 - 2 - 5) = 10
- AND the target's health is reduced by 10

### Scenario: Ranged attack
- GIVEN attacker with `intelligence=50` wielding `bow` (damage 4) and 3 arrows, target at distance 4 tiles
- WHEN the attacker executes ATTACK on the target
- THEN damage = max(1, 4 + (50 * 0.1) - target.armor_rating)
- AND the attacker's inventory loses 1 arrow

### Scenario: Ranged attack — out of range
- GIVEN attacker with bow targeting an agent 6 tiles away
- WHEN the attacker executes ATTACK
- THEN the action returns `success=False` with reason "target out of range"

### Scenario: Ranged attack — no arrows
- GIVEN attacker with bow wielding but 0 arrows in inventory
- WHEN the attacker executes ATTACK
- THEN the action returns `success=False` with reason "no ammunition"

### Scenario: Guard reduces damage
- GIVEN a guarding agent (is_guarding=True) with armor_rating=2
- WHEN an attacker deals 10 base damage
- THEN the guard reduces damage to max(1, round(10 * 0.5)) = 5, then armor reduces to max(1, 5 - 2) = 3
- AND the target takes 3 damage instead of 8 (unguarded with armor)

### Scenario: Combat death
- GIVEN a target agent with health=8
- WHEN an attacker deals 10 damage
- THEN the target's health reaches -2
- AND the target dies with `cause="combat"`
- AND a `combat_death` SimEvent is logged with the attacker's name and the target's name

### Scenario: Self-attack prevention
- GIVEN an agent with id="agent_001"
- WHEN the agent executes ATTACK with target_id="agent_001"
- THEN the action returns `success=False` with reason "cannot attack self"

### Scenario: FSM interruption on damage
- GIVEN an agent in `executing` state gathering berries
- WHEN the agent takes combat damage
- THEN the agent's FSM transitions to `evaluate`
- AND the agent can decide to retaliate or flee on the next tick

### Scenario: Equipment in snapshot
- GIVEN an agent with weapon="spear" and armor="hide_vest"
- WHEN a WorldSnapshot is built
- THEN the agent's AgentState includes `equipment={"weapon": "spear", "armor": "hide_vest", "tool": "none"}`

### Scenario: Unequipped defaults
- GIVEN a newly created agent with no equipment specified
- WHEN the agent is initialized
- THEN `agent.equipment` is `{"weapon": "fist", "armor": "none", "tool": "none"}`
