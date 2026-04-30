# Delta for agent-society

> Modifies the agent-society spec from `openspec/specs/agent-society/spec.md`.
> Adds 10 new ActionTypes, equipment fields on Agent, role-specific behavioral context in prompts, structure awareness in prompts, and new fields in snapshots/schemas.

## ADDED Requirements

### Requirement: New ActionTypes in Agent Society

The `ActionType` enum SHALL be extended with 10 new values: MINE, HUNT, FISH, FARM, CRAFT, BUILD, ATTACK, GUARD, EXPLORE, HEAL. These SHALL be registered in `REGISTRY`, `ACTION_EMOJIS`, and `get_action_duration()`.
(Previously: 10 action types. Now: 20.)

#### Scenario: New ActionType enum values
- GIVEN the ActionType enum
- WHEN checking for MINE, HUNT, FISH, FARM, CRAFT, BUILD, ATTACK, GUARD, EXPLORE, HEAL
- THEN each exists as a valid member

### Requirement: Agent Equipment Fields

The `Agent` dataclass SHALL gain an `equipment` field: `equipment: dict[str, str]` with keys `weapon`, `armor`, `tool`. Default values: `{"weapon": "fist", "armor": "none", "tool": "none"}`. These SHALL be serialized in the `AgentState` Pydantic model and included in the WebSocket snapshot.

#### Scenario: Agent defaults
- GIVEN a newly created Agent
- WHEN the agent is initialized
- THEN `agent.equipment` is `{"weapon": "fist", "armor": "none", "tool": "none"}`

#### Scenario: Equipment in snapshot
- GIVEN an agent with `equipment={"weapon": "spear", "armor": "hide_vest", "tool": "stone_axe"}`
- WHEN a WorldSnapshot is built
- THEN the agent's AgentState includes the `equipment` field with the same values

### Requirement: Role-Specific Behavioral Context in LLM Prompts

The LLM prompt builder SHALL include role-specific behavioral guidance. Each role's description, allowed actions, and priority intent SHALL appear in both the system prompt and the state prompt context. The `JSON_FORMAT_INSTRUCTION` SHALL include the 10 new actions in the steps action enum.

#### Scenario: Role context in system prompt
- GIVEN an agent with role `hunter`
- WHEN `build_agent_prompt()` is called
- THEN the system prompt includes role-specific guidance (e.g., "As a hunter, you track and hunt animals for food and hide.")

#### Scenario: New actions in JSON format instruction
- GIVEN the `JSON_FORMAT_INSTRUCTION`
- WHEN inspected
- THEN the steps action enum includes "mine", "hunt", "fish", "farm", "craft", "build", "attack", "guard", "explore", "heal"

### Requirement: Structure Awareness in LLM Prompts

The LLM prompt SHALL include context about nearby structures: their type, position, owner, and health. This context SHALL appear in the state prompt template alongside nearby resources.

#### Scenario: Structure context in prompt
- GIVEN an agent near a forge structure at position (12,12) and a farm at (15,15)
- WHEN the LLM prompt is built
- THEN the prompt includes a `NEARBY STRUCTURES:` section listing the forge and farm with their positions

### Requirement: Equipment in AgentState Schema

The `AgentState` Pydantic model SHALL gain an `equipment: dict[str, str]` field.

#### Scenario: Equipment field in schema
- GIVEN an AgentState created from an agent with equipment
- WHEN the AgentState is serialized to JSON
- THEN the JSON includes `"equipment": {"weapon": "...", "armor": "...", "tool": "..."}`

### Requirement: Structures in WorldSnapshot Schema

The `WorldSnapshot` Pydantic model SHALL gain an optional `structures: list[dict]` field. Each structure dict SHALL contain: `id`, `type`, `position`, `owner_id`, `health`, `max_health`, and `properties`.

#### Scenario: Structures field in snapshot
- GIVEN a WorldSnapshot built with 2 active structures
- WHEN the snapshot is serialized
- THEN the `structures` list contains both structure dicts with all specified fields

## MODIFIED Requirements

### Colony Information Panel (F7) — Extended Metrics

The colony stats SHALL include additional fields: total structures count, structures by type, total equipment (weapons/armor held by all agents).
(Previously: population, births, deaths, total resources, factions.)

#### Scenario: Structures in colony stats
- GIVEN a simulation with 5 structures (2 houses, 1 forge, 1 farm, 1 wall)
- WHEN `GET /api/colony` is called
- THEN the response includes `total_structures=5` and `structures_by_type={"house": 2, "forge": 1, "farm": 1, "wall": 1}`
