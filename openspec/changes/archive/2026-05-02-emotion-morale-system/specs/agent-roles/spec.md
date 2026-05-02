# Delta: agent-roles (Modified)

## MODIFIED Requirements

### R5 — Agent Emotions Field

The Agent dataclass MUST gain an `emotions: dict[str, dict]` field (default empty dict). Each entry maps emotion name → `{"intensity": float, "last_trigger_tick": int}`. The AgentState schema MUST mirror this field.
(Previously: Agent had no emotions field.)

#### Scenario: New agent has empty emotions
- GIVEN a new Agent created via AgentFactory.from_config()
- WHEN the agent is initialized
- THEN agent.emotions == {}

#### Scenario: Snapshot includes emotions
- GIVEN an agent with emotions={"happy": {"intensity": 0.7, "last_trigger_tick": 42}}
- WHEN WorldSnapshotBuilder.build() is called
- THEN the resulting AgentState includes `emotions: {"happy": {"intensity": 0.7, "last_trigger_tick": 42}}`
