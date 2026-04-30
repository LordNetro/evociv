# Spec: crafting-system

## Purpose

Define a data-driven crafting system with a recipe registry, tool/item modifiers, workbench requirements, and the CRAFT action. Enables agents to transform raw resources into tools, weapons, armor, building materials, and advanced items.

## Dependencies

- **Depends on**: agent-roles, resources-extended, structures

## Capabilities

### capability: crafting-system
**Depends on**: agent-roles, resources-extended, structures

#### Requirements

| # | Requirement | Strength |
|---|-------------|----------|
| R1 | The system MUST maintain a recipe registry loaded from `config/recipes.json`. Each recipe MUST have: `id`, `name`, `category` (tool/weapon/armor/material/food), `inputs` (resource -> qty), `outputs` (resource -> qty), `duration` (ticks), `tool_required` (optional, list of tool types), `station_required` (optional, structure type), `skill_required` (optional, minimum skill level). | MUST |
| R2 | A new `CRAFT` ActionType MUST be added to the enum and registered in the REGISTRY. The handler receives a `recipe_id` from the plan step. | MUST |
| R3 | The CRAFT handler MUST verify all requirements before execution: (a) agent has sufficient inputs in inventory, (b) agent has required tool equipped (if specified), (c) agent is adjacent to required station structure (if specified), (d) agent's relevant skill meets minimum (if specified). If any check fails, the action MUST return `success=False` with a descriptive reason. | MUST |
| R4 | On successful craft, inputs MUST be consumed from inventory, outputs MUST be added to inventory, and the action MUST return `success=True` with a summary of what was produced. Consumption and production MUST be atomic. | MUST |
| R5 | Equipped tools MAY modify craft outcomes: a higher-quality tool (e.g., iron axe vs stone axe) SHALL reduce `duration` by up to 50% or increase output quantity by up to 25% (tool-dependent). The modifier formula MUST be configurable per tool. | SHOULD |
| R6 | Crafting a recipe at a station (forge, workbench) MUST be faster than crafting without one: station reduces `duration` by 30% (minimum 1 tick). | SHOULD |
| R7 | The recipe registry MUST include at least these recipes: `planks` (2 wood -> 4 planks, at workbench), `stone_blade` (2 stone -> 1 stone_blade, at workbench), `rope` (3 fiber -> 1 rope), `spear` (1 stone_blade + 2 wood -> 1 spear, at workbench), `bow` (2 wood + 1 rope -> 1 bow, at workbench), `hide_vest` (3 hide -> 1 hide_vest), `stone_axe` (1 stone_blade + 1 wood -> 1 stone_axe, at workbench), `iron_ingot` (2 iron_ore + 1 clay -> 1 iron_ingot, at forge), `iron_sword` (2 iron_ingot + 1 wood -> 1 iron_sword, at forge), `bone_armor` (5 bone + 2 rope -> 1 bone_armor), `arrow` (1 wood + 1 stone -> 3 arrows). | MUST |
| R8 | The LLM prompt MUST include the agent's knowledge of available recipes (what they can craft with current inventory) so the LLM can make informed crafting decisions. | MUST |
| R9 | The CRAFT action duration MUST be calculated from the recipe's base `duration` modified by tool quality and station bonus, plus agent intelligence (higher intelligence reduces craft time). | SHOULD |

#### Scenarios

### Scenario: Simple craft at workbench
- GIVEN an agent with `inventory={"wood": 2}` adjacent to a workbench structure
- WHEN the agent executes CRAFT with `recipe_id="planks"`
- THEN inventory changes: wood:-2, planks:+4, and the action returns `success=True`

### Scenario: Craft with tool requirement
- GIVEN an agent with `inventory={"fiber": 3}` but no tool equipped
- WHEN the agent executes CRAFT with `recipe_id="rope"`
- THEN the action returns `success=True` (rope has no tool requirement)

### Scenario: Craft with station requirement — missing station
- GIVEN an agent with `inventory={"iron_ore": 2, "clay": 1}` but no forge nearby
- WHEN the agent executes CRAFT with `recipe_id="iron_ingot"`
- THEN the action returns `success=False` with reason "requires forge station"

### Scenario: Craft with insufficient inputs
- GIVEN an agent with `inventory={"wood": 1}`
- WHEN the agent executes CRAFT with `recipe_id="planks"` (requires 2 wood)
- THEN the action returns `success=False` with reason "insufficient inputs: wood"

### Scenario: Tool modifier reduces duration
- GIVEN an agent with an iron_axe equipped (quality modifier: duration x 0.5) crafting `recipe_id="planks"` (base duration 10)
- WHEN the CRAFT action is processed
- THEN the effective duration is 5 ticks (or the modified value based on tool bonus)

### Scenario: Atomic craft rollback
- GIVEN an agent with `inventory={"wood": 2}` crafting `recipe_id="planks"`
- WHEN the craft succeeds
- THEN inventory shows exactly `{"wood": 0, "planks": 4}` — no partial state

### Scenario: LLM aware of craftable recipes
- GIVEN an agent with `inventory={"wood": 2, "stone": 2}` adjacent to a workbench
- WHEN the LLM prompt is built
- THEN the prompt includes that the agent can craft "stone_blade" and "planks" given current inventory
