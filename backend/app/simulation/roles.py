"""Role helpers — lookup, stat application, and action restriction."""

from __future__ import annotations

from app.core.definitions import DEFINITIONS
from app.simulation.agent import Agent
from app.simulation.actions import ActionType


ROLES = DEFINITIONS.roles
DEFAULT_ROLE = DEFINITIONS.default_role


def get_role_config(role_name: str) -> dict:
    """Return the configuration dict for *role_name*.

    Falls back to :data:`DEFAULT_ROLE` if the name is unknown.
    """
    role = ROLES.get(role_name, ROLES[DEFAULT_ROLE])
    # Convert RoleDef model to plain dict for backward-compatible dict access
    return role.model_dump()


def apply_role_stats(agent: Agent) -> None:
    """Apply stat modifiers from the agent's role at creation time."""
    config = get_role_config(agent.role)
    agent.role_data = config
    for stat, delta in config.get("stat_modifiers", {}).items():
        current = getattr(agent, stat, 0)
        setattr(agent, stat, max(0, min(100, current + delta)))


def role_allows_action(role_name: str, action_type: ActionType | str) -> bool:
    """Check whether *role_name* may perform *action_type*."""
    config = get_role_config(role_name)
    allowed = config.get("allowed_actions", [])
    action_str = action_type.value if isinstance(action_type, ActionType) else str(action_type)
    return action_str in allowed
