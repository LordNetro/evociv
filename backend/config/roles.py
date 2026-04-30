"""Role configuration — data-driven behavior definitions."""

from __future__ import annotations

# Role definitions drive agent behavior via priority tables.
# Each role specifies:
#   priorities:      [(action_name, score), ...] — higher score = higher priority
#   allowed_actions: [action_name, ...] — actions this role may perform
#   stat_modifiers:  {stat: delta} — applied at agent creation
#   tool_allowlist:  [item_name, ...] — optional required tools

ROLES: dict[str, dict] = {
    "gatherer": {
        "priorities": [],
        "allowed_actions": [
            "move", "gather", "eat", "drink", "rest", "explore",
            "trade", "socialize", "feed_child",
        ],
        "stat_modifiers": {"speed": 5},
        "tool_allowlist": [],
    },
    "hunter": {
        "priorities": [
            ("hunt", 80),
            ("gather", 60),
            ("eat", 60),
            ("drink", 60),
            ("rest", 40),
            ("explore", 30),
        ],
        "allowed_actions": [
            "move", "hunt", "gather", "eat", "drink", "rest", "explore",
            "trade", "socialize", "feed_child",
        ],
        "stat_modifiers": {"strength": 10, "speed": 5},
        "tool_allowlist": ["spear"],
    },
    "fisher": {
        "priorities": [
            ("fish", 80),
            ("gather", 60),
            ("eat", 60),
            ("drink", 60),
            ("rest", 40),
        ],
        "allowed_actions": [
            "move", "fish", "gather", "eat", "drink", "rest",
            "trade", "socialize", "feed_child",
        ],
        "stat_modifiers": {"intelligence": 5},
        "tool_allowlist": ["spear"],
    },
    "farmer": {
        "priorities": [
            ("farm", 80),
            ("gather", 60),
            ("eat", 60),
            ("drink", 60),
            ("rest", 40),
        ],
        "allowed_actions": [
            "move", "farm", "gather", "eat", "drink", "rest", "build",
            "trade", "socialize", "feed_child",
        ],
        "stat_modifiers": {"intelligence": 10},
        "tool_allowlist": [],
    },
    "miner": {
        "priorities": [
            ("mine", 80),
            ("gather", 60),
            ("eat", 60),
            ("drink", 60),
            ("rest", 40),
            ("explore", 30),
        ],
        "allowed_actions": [
            "move", "mine", "gather", "eat", "drink", "rest", "explore",
            "trade", "socialize", "feed_child",
        ],
        "stat_modifiers": {"strength": 10},
        "tool_allowlist": ["pickaxe"],
    },
    "builder": {
        "priorities": [
            ("build", 80),
            ("gather", 60),
            ("eat", 60),
            ("drink", 60),
            ("rest", 40),
        ],
        "allowed_actions": [
            "move", "build", "gather", "eat", "drink", "rest",
            "trade", "socialize", "feed_child",
        ],
        "stat_modifiers": {"strength": 10},
        "tool_allowlist": [],
    },
    "crafter": {
        "priorities": [
            ("craft", 80),
            ("gather", 60),
            ("eat", 60),
            ("drink", 60),
            ("rest", 40),
        ],
        "allowed_actions": [
            "move", "craft", "gather", "eat", "drink", "rest",
            "trade", "socialize", "feed_child",
        ],
        "stat_modifiers": {"intelligence": 15},
        "tool_allowlist": [],
    },
    "scout": {
        "priorities": [
            ("explore", 90),
            ("gather", 60),
            ("eat", 60),
            ("drink", 60),
            ("rest", 40),
        ],
        "allowed_actions": [
            "move", "explore", "gather", "eat", "drink", "rest",
            "trade", "socialize", "feed_child",
        ],
        "stat_modifiers": {"speed": 15},
        "tool_allowlist": [],
    },
    "fighter": {
        "priorities": [
            ("attack", 80),
            ("guard", 70),
            ("gather", 60),
            ("eat", 60),
            ("drink", 60),
            ("rest", 40),
        ],
        "allowed_actions": [
            "move", "attack", "guard", "gather", "eat", "drink", "rest",
            "trade", "socialize", "feed_child",
        ],
        "stat_modifiers": {"strength": 15, "speed": 5},
        "tool_allowlist": [],
    },
    "healer": {
        "priorities": [
            ("heal", 80),
            ("gather", 60),
            ("eat", 60),
            ("drink", 60),
            ("rest", 40),
        ],
        "allowed_actions": [
            "move", "heal", "gather", "eat", "drink", "rest",
            "trade", "socialize", "feed_child",
        ],
        "stat_modifiers": {"intelligence": 10, "sociability": 5},
        "tool_allowlist": [],
    },
}

DEFAULT_ROLE = "gatherer"
