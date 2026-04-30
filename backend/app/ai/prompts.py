"""Prompt templates for agent LLM interactions."""

from typing import Any

from app.simulation.agent import Agent

ROLE_GUIDANCE: dict[str, str] = {
    "gatherer": "As a gatherer, your priority is collecting resources for the tribe. Gather berries, wood, fiber, and other materials.",
    "hunter": "As a hunter, your priority is hunting animals for meat and hide. Use spears or bows to hunt deer, rabbits, and boars.",
    "fisher": "As a fisher, your priority is fishing for food. Use a fishing rod near water sources.",
    "farmer": "As a farmer, your priority is farming crops. Build and maintain farms to produce berries and fiber.",
    "miner": "As a miner, your priority is mining stone and iron ore. Use pickaxes to extract minerals.",
    "builder": "As a builder, your priority is constructing buildings for the tribe. Gather wood and stone to build houses, walls, and workbenches.",
    "crafter": "As a crafter, your priority is crafting tools and weapons. Gather materials and use workbenches to create better equipment.",
    "scout": "As a scout, your priority is exploring the world. Discover new resources and territories for the tribe.",
    "fighter": "As a fighter, your priority is defending the tribe and engaging in combat. Use weapons and armor to protect your people.",
    "healer": "As a healer, your priority is healing injured tribe members. Gather berries and use your intelligence to restore health.",
}


SYSTEM_PROMPT_TEMPLATE = """You are {name}, a {role} in a tribal society.

Your personality:
{personality}

You live in a 50x50 grid world with resources like trees (for wood), water, berries (for food), stone, iron ore, clay, sand, fiber, and animals (deer, rabbit, boar).
You can move, chop trees, drink water, eat berries, gather resources, rest, mine minerals, explore unknown areas, craft tools and weapons, hunt animals, fish, build structures, farm crops, attack enemies, guard yourself, heal, trade with others, socialize, and feed children.
Structures such as workbenches, forges, houses, walls, and farms can be built to support the tribe.
Crafting tools like axes, pickaxes, spears, and fishing rods improves your efficiency.

RULES:
- You MUST respond ONLY with a valid JSON object. No other text.
- Your goal is to survive and help your tribe prosper.
- If you have a critical need (hunger > 85 or thirst > 85), address it IMMEDIATELY.
- You can form relationships with other agents you encounter.
- Think about what would benefit both you and the group."""

STATE_PROMPT_TEMPLATE = """CURRENT STATE:
- Position: ({x:.0f}, {y:.0f})
- Hunger: {hunger:.0f}/100 (0 = full, 100 = starving)
- Thirst: {thirst:.0f}/100 (0 = hydrated, 100 = dehydrated)
- Energy: {energy:.0f}/100
- Health: {health:.0f}/100
- Inventory: {inventory}
- Current action: {action}

EQUIPMENT:
{equipment}

LAST ACTION RESULT:
{last_action_result}

NEARBY RESOURCES: {resources}

NEARBY STRUCTURES: {nearby_structures}

CRAFTABLE RECIPES:
{craftable_recipes}

NEARBY HOSTILES:
{nearby_hostiles}

KNOWLEDGE:
{knowledge}

NEARBY AGENTS: {agents}

SOCIAL CONTEXT:
{social_context}

FACTION:
{faction_context}

RECENT MEMORIES:
{memories}

TRIGGER: {trigger}"""

JSON_FORMAT_INSTRUCTION = """
Respond with ONLY this JSON format:
{
  "reasoning": "One sentence explaining your decision",
  "intention": "What you want to achieve",
  "priority": "low" | "medium" | "high",
  "steps": [
    {
      "action": "move" | "chop" | "drink" | "eat" | "gather" | "rest" | "mine" | "explore" | "craft" | "hunt" | "fish" | "build" | "farm" | "attack" | "guard" | "heal" | "trade" | "socialize" | "feed_child",
      "target": [x, y] or null,
      "reason": "Why this step"
    }
  ],
  "abort_if": {
    "hunger < 15": "what to do if starving",
    "thirst < 15": "what to do if dehydrated"
  },
  "think_aloud": "Your internal monologue as narration",
  "say_to": {"agent_id": "target_agent_id", "text": "What you want to say to another agent"} | null
}

IMPORTANT: "move" to get to resources, then use the appropriate action.
If you are already near a resource, use its action directly without moving first.
Keep plans to 2-4 steps maximum.
"""


def _get_craftable_recipes(agent: Agent) -> str:
    """Return a formatted list of recipes the agent can craft with current inventory."""
    from app.simulation.crafting import RECIPES
    from app.simulation.roles import role_allows_action
    from app.simulation.actions import ActionType

    if not role_allows_action(agent.role, ActionType.CRAFT):
        return ""

    craftable: list[str] = []
    for name, recipe in RECIPES.items():
        if all(agent.inventory.get(item, 0) >= qty for item, qty in recipe.inputs.items()):
            craftable.append(
                f"- {name} ({recipe.category}): {recipe.inputs} -> {recipe.output}"
            )
    return "\n".join(craftable)


def build_agent_prompt(
    agent: Agent,
    nearby_resources: str,
    nearby_agents: str,
    memories: str,
    trigger: str,
    last_action_result: Any = None,
    social_context: str = "",
    faction_context: str = "",
    nearby_structures: str = "",
    craftable_recipes: str = "",
    equipment: str = "",
    nearby_hostiles: str = "",
) -> str:
    """Build the full prompt for an agent LLM call."""
    personality = agent.__dict__.get("system_prompt", "") or (
        f"You are a {agent.role}. "
        f"You have strength={agent.strength}, intelligence={agent.intelligence}, "
        f"sociability={agent.sociability}, speed={agent.speed}."
    )

    # Format last action result
    if last_action_result is None:
        lar_str = "None (first tick)"
    else:
        from app.simulation.actions import ActionResult
        if isinstance(last_action_result, ActionResult):
            lar_str = (
                f"- Action: {last_action_result.action_type}\n"
                f"- Success: {last_action_result.success}\n"
                f"- Effects: {last_action_result.action_summary}"
            )
        else:
            lar_str = str(last_action_result)

    # Format social context
    if not social_context:
        if agent.conversation_queue:
            count = len(agent.conversation_queue)
            latest = agent.conversation_queue[-1]
            social_str = f"- Unread messages: {count}\n- Latest: {latest.content}"
        else:
            social_str = "- No pending messages"
    else:
        social_str = social_context

    # Format faction context
    if not faction_context:
        if agent.faction_id:
            faction_str = f'- You are a member of faction "{agent.faction_id}"'
        else:
            faction_str = "- You are not in a faction"
    else:
        faction_str = faction_context

    system = SYSTEM_PROMPT_TEMPLATE.format(name=agent.name, role=agent.role, personality=personality)

    # Append role-specific guidance
    role_guidance = ROLE_GUIDANCE.get(agent.role, "")
    if role_guidance:
        system = f"{system}\n\n{role_guidance}"

    # Format knowledge
    if agent.knowledge:
        knowledge_str = "\n".join(
            f"- You know: {subtype} is {props}"
            for subtype, props in agent.knowledge.items()
        )
    else:
        knowledge_str = "(you have no special knowledge yet)"

    # Format nearby structures
    structures_str = nearby_structures if nearby_structures else "(none)"

    # Format craftable recipes
    recipes_str = craftable_recipes if craftable_recipes else "(none)"

    # Format equipment
    equipment_str = equipment if equipment else "(none)"

    # Format nearby hostiles
    hostiles_str = nearby_hostiles if nearby_hostiles else "(none)"

    state = STATE_PROMPT_TEMPLATE.format(
        x=agent.position[0],
        y=agent.position[1],
        hunger=agent.hunger,
        thirst=agent.thirst,
        energy=agent.energy,
        health=agent.health,
        inventory=agent.inventory or {},
        action=agent.current_action or "idle",
        equipment=equipment_str,
        last_action_result=lar_str,
        resources=nearby_resources,
        nearby_structures=structures_str,
        craftable_recipes=recipes_str,
        nearby_hostiles=hostiles_str,
        knowledge=knowledge_str,
        agents=nearby_agents,
        social_context=social_str,
        faction_context=faction_str,
        memories=memories,
        trigger=trigger,
    )

    return f"{system}\n\n{state}\n\n{JSON_FORMAT_INSTRUCTION}"
