"""Prompt templates for agent LLM interactions."""

from app.simulation.agent import Agent

SYSTEM_PROMPT_TEMPLATE = """You are {name}, a {role} in a tribal society.

Your personality:
{personality}

You live in a 50x50 grid world with resources like trees (for wood), water, berries (for food), and stone.
You can move, chop trees, drink water, eat berries, gather resources, and rest.

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

NEARBY RESOURCES: {resources}

NEARBY AGENTS: {agents}

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
      "action": "move" | "chop" | "drink" | "eat" | "gather" | "rest",
      "target": [x, y] or null,
      "duration_secs": number (1-30),
      "reason": "Why this step"
    }
  ],
  "abort_if": {
    "hunger < 15": "what to do if starving",
    "thirst < 15": "what to do if dehydrated"
  },
  "think_aloud": "Your internal monologue as narration"
}

IMPORTANT: "move" to get to resources, then use the appropriate action.
If you are already near a resource, use its action directly without moving first.
Keep plans to 2-4 steps maximum.
"""


def build_agent_prompt(
    agent: Agent,
    nearby_resources: str,
    nearby_agents: str,
    memories: str,
    trigger: str,
) -> str:
    """Build the full prompt for an agent LLM call."""
    personality = agent.__dict__.get("system_prompt", "") or (
        f"You are a {agent.role}. "
        f"You have strength={agent.strength}, intelligence={agent.intelligence}, "
        f"sociability={agent.sociability}, speed={agent.speed}."
    )

    system = SYSTEM_PROMPT_TEMPLATE.format(name=agent.name, role=agent.role, personality=personality)

    state = STATE_PROMPT_TEMPLATE.format(
        x=agent.position[0],
        y=agent.position[1],
        hunger=agent.hunger,
        thirst=agent.thirst,
        energy=agent.energy,
        health=agent.health,
        inventory=agent.inventory or {},
        action=agent.current_action or "idle",
        resources=nearby_resources,
        agents=nearby_agents,
        memories=memories,
        trigger=trigger,
    )

    return f"{system}\n\n{state}\n\n{JSON_FORMAT_INSTRUCTION}"
