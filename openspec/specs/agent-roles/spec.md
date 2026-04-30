# Spec: agent-roles

## Purpose

Define data-driven role definitions that determine agent behavior: action priority tables, allowed actions, base attribute modifiers, and role-specific LLM context. Roles replace the current hardcoded FSM priority ordering with configurable, role-driven decision-making.

## Dependencies

- **Depends on**: simulation-engine

## Capabilities

### capability: agent-roles
**Depends on**: simulation-engine

#### Requirements

| # | Requirement | Strength |
|---|-------------|----------|
| R1 | The system MUST define roles as data (config dict or JSON file) with fields: `id`, `name`, `description`, `base_attributes` (stat modifiers), `action_priorities` (ordered list of need/action pairs), `allowed_actions` (list of ActionType values), and `default_equipment` (optional weapon/armor/tool). | MUST |
| R2 | The `action_priorities` table per role MUST determine the evaluation order in the agent's FSM. Higher-priority items are checked first regardless of need thresholds. | MUST |
| R3 | Each role's `allowed_actions` list MUST restrict which ActionTypes the agent can execute. Actions not in the list MUST be rejected at the FSM level before the handler is called. | MUST |
| R4 | Role `base_attributes` MUST apply stat modifiers on agent creation (e.g., `gatherer: +10 speed`, `fighter: +10 strength`, `builder: +10 intelligence`). | MUST |
| R5 | The Agent dataclass MUST gain a `role_data: dict` field that caches the resolved role definition for the current tick to avoid repeated lookups. | MUST |
| R6 | The LLM prompt MUST include the agent's role description, allowed actions, and role-specific behavioral guidance (e.g., "As a fighter, you prefer direct confrontation"). | MUST |
| R7 | The factory MUST support role assignment via config dict. If no role is specified, `gatherer` is the default. | MUST |
| R8 | Default roles MUST include: `gatherer`, `hunter`, `fisher`, `farmer`, `miner`, `builder`, `crafter`, `scout`, `fighter`, `healer`. Each with distinct priority tables and allowed actions. | MUST |

#### Role Priority Tables

##### gatherer
Priorities: GATHER (food) > CHOP (wood) > MOVE > REST > LLM

Allowed actions: MOVE, GATHER, CHOP, EAT, DRINK, REST, SOCIALIZE, TRADE

Base: speed +10, strength +0

##### hunter
Priorities: HUNT (food) > CRAFT (tools/weapons) > ATTACK > MOVE > REST > LLM

Allowed actions: MOVE, HUNT, CRAFT, ATTACK, EAT, DRINK, REST, SOCIALIZE, TRADE

Base: strength +10, speed +5

##### fisher
Priorities: FISH (food) > MOVE > REST > CRAFT > LLM

Allowed actions: MOVE, FISH, CRAFT, EAT, DRINK, REST, SOCIALIZE, TRADE

Base: intelligence +5, speed +5

##### farmer
Priorities: FARM (food) > BUILD (farm structures) > GATHER > REST > LLM

Allowed actions: MOVE, FARM, BUILD, GATHER, EAT, DRINK, REST, SOCIALIZE, TRADE

Base: intelligence +10, strength +5

##### miner
Priorities: MINE (resources) > MOVE > CRAFT > REST > LLM

Allowed actions: MOVE, MINE, CRAFT, EAT, DRINK, REST, SOCIALIZE, TRADE

Base: strength +15, speed -5

##### builder
Priorities: BUILD (structures) > CHOP (wood) > MINE > MOVE > REST > LLM

Allowed actions: MOVE, BUILD, CHOP, MINE, CRAFT, EAT, DRINK, REST, SOCIALIZE, TRADE

Base: strength +10, intelligence +5

##### crafter
Priorities: CRAFT (items) > MINE > CHOP > GATHER > MOVE > REST > LLM

Allowed actions: MOVE, CRAFT, MINE, CHOP, GATHER, EAT, DRINK, REST, SOCIALIZE, TRADE

Base: intelligence +15, speed -5

##### scout
Priorities: EXPLORE > MOVE > GATHER > REST > LLM

Allowed actions: MOVE, EXPLORE, GATHER, EAT, DRINK, REST, SOCIALIZE, TRADE

Base: speed +15, strength -5

##### fighter
Priorities: GUARD > ATTACK > MOVE > HUNT > REST > CRAFT > LLM

Allowed actions: MOVE, ATTACK, GUARD, HUNT, CRAFT, EAT, DRINK, REST, SOCIALIZE, TRADE

Base: strength +15, intelligence +5

##### healer
Priorities: HEAL > GATHER (herbs) > MOVE > REST > LLM

Allowed actions: MOVE, HEAL, GATHER, EAT, DRINK, REST, SOCIALIZE, TRADE, CRAFT

Base: intelligence +10, sociability +10

#### Scenarios

### Scenario: Role-appropriate action priority
- GIVEN a `fighter` agent and a `gatherer` agent both at hunger=50, energy=30, with no threats nearby
- WHEN the FSM evaluates priorities for both
- THEN the fighter prioritizes GUARD > ATTACK (role highest priorities), while the gatherer prioritizes GATHER > REST

### Scenario: Role action restriction
- GIVEN a `gatherer` agent with no `ATTACK` in its `allowed_actions`
- WHEN the FSM tries to execute ATTACK (e.g., from an LLM plan)
- THEN the action is rejected at the FSM level with `success=False` and the FSM transitions to "evaluate"

### Scenario: Role base attributes applied
- GIVEN an agent created with role `fighter`
- WHEN the agent is initialized
- THEN the agent has `strength=65` (50 base + 15 role bonus) and `speed=55` (50 base + 5 role bonus)

### Scenario: Default role fallback
- GIVEN an agent config with no `role` field
- WHEN the factory creates the agent
- THEN the agent's role is `gatherer`

### Scenario: LLM receives role context
- GIVEN an agent with role `hunter`
- WHEN the LLM prompt is built
- THEN the prompt includes role description, available actions (including HUNT, ATTACK), and behavioral guidance matching the hunter role

### Scenario: Unknown role rejection
- GIVEN an agent config with role=`wizard`
- WHEN the factory attempts to create the agent
- THEN a `ValueError` is raised or the agent falls back to `gatherer` with a logged warning
