# FSM Core Specification

## Purpose

The FSM core governs agent behavior state transitions, LLM decision integration,
director mode interaction, and state lifecycle cleanup. This spec establishes
stability guarantees for the simulation engine's finite state machine —
eliminating race conditions, resource leaks, and incomplete resets.

## Requirements

### Requirement: LLM Response Processing — Single Handler

The system SHALL process all completed LLM responses exclusively through
`_poll_llm_responses`. `_fsm_llm_waiting` SHALL NOT process LLM results —
it SHALL only handle instinct actions (eat, rest, move).

When a response arrives for an agent NOT in `llm_waiting`, the poll path SHALL
set the plan but NOT transition the agent's FSM. When a response arrives for
an agent IN `llm_waiting`, the poll path SHALL set the plan AND transition the
agent to `evaluate`.

#### Scenario: Response during llm_waiting

- GIVEN an agent is in `llm_waiting` with `llm_call_pending = True`
- WHEN the LLM response completes
- THEN `_poll_llm_responses` applies the plan and transitions the agent to `evaluate`
- AND `_fsm_llm_waiting` does NOT process the future result

#### Scenario: Response arrives for non-waiting agent

- GIVEN an agent has a pending LLM call but left `llm_waiting` (e.g., interrupted by director command)
- WHEN the LLM response completes
- THEN `_poll_llm_responses` sets the plan on the agent
- BUT does NOT transition the agent's FSM state

### Requirement: LLM Task Cancellation

When a director command cancels an LLM future, the background task SHALL also
be cancelled. Both `RealLLMOrchestrator._resolve()` and
`MockLLMOrchestrator._resolve()` SHALL release the semaphore via `finally`.

#### Scenario: Director preempts LLM call

- GIVEN an agent has a pending LLM future AND a running background task
- WHEN a director command preempts the agent
- THEN the future AND the background task SHALL both be cancelled
- AND the semaphore SHALL be released (ensured by `finally`)

#### Scenario: Mock orchestrator cancellation

- GIVEN `MockLLMOrchestrator._resolve()` is running for an agent
- WHEN the background task is cancelled
- THEN the task exits gracefully without leaking pending state

### Requirement: LLM Cooldown Guard

The cooldown check SHALL happen BEFORE entering `_fsm_llm_trigger`.
If cooldown is active (tick - last < 30 ticks) and the agent would enter
`llm_trigger`, the FSM SHALL skip directly to `evaluate`.

#### Scenario: Cooldown prevents LLM trigger

- GIVEN an agent's `_last_llm_tick` is less than 30 ticks ago
- WHEN `_run_agent_fsm` dispatches to `llm_trigger`
- THEN the agent skips `_fsm_llm_trigger` and transitions directly to `evaluate`

### Requirement: Complete Reset on Release

`release_all` SHALL reset ALL agent state — cancel pending LLM futures, clear
plans, actions, positions, paths, injected thoughts, and LLM cooldown.
`release` (single agent) SHALL clear the same fields for one agent and
transition it to `evaluate`.

#### Scenario: release_all full reset

- GIVEN multiple agents have active plans, actions, pending LLM calls, injected thoughts
- WHEN `release_all` is issued
- THEN ALL pending LLM futures are cancelled for all agents
- AND `active_plan`, `plan_step_index`, `current_action`, `current_action_emoji`, `action_duration`, `action_progress`, `target_position`, `move_path`, `injected_thoughts` are cleared for all agents
- AND `_last_llm_tick` is reset for all agents
- AND `director_mode` is False

#### Scenario: release single agent

- GIVEN an agent in director mode has an active plan and action
- WHEN `release` is issued for that agent
- THEN `active_plan`, `current_action`, `target_position`, `move_path` are cleared
- AND the agent transitions to `evaluate`

### Requirement: Natural Reproduction Flow

An agent SHALL NOT directly mutate another agent's FSM during reproduction.
The partner SHALL detect the reproduction request during its own `evaluate`
cycle on the next tick through internal flags.

#### Scenario: Reproduction without cross-agent mutation

- GIVEN an agent finds a compatible partner and initiates reproduction
- WHEN the originating agent sets `_is_reproducing` and transitions to `executing`
- THEN the partner's FSM state SHALL NOT be directly modified
- AND the partner SHALL react during its own `evaluate` on the next tick

### Requirement: Atomic Action Field Management

All action fields (`current_action`, `current_action_emoji`, `action_duration`,
`action_progress`) SHALL be reset atomically. `current_action_emoji` SHALL be
set whenever `current_action` is set and cleared whenever `current_action` is
cleared.

#### Scenario: Action completion clears emoji

- GIVEN an agent completes an action in `_fsm_executing`
- WHEN `current_action` is cleared
- THEN `current_action_emoji`, `action_duration`, `action_progress` are cleared simultaneously

#### Scenario: do_action sets emoji

- GIVEN a director issues `do_action` with an action ID
- WHEN `current_action` is set to the action ID
- THEN `current_action_emoji` is set to the corresponding emoji

## Coverage Summary

| Domain | Requirements | Scenarios |
|--------|-------------|-----------|
| LLM Response Processing | 1 | 2 |
| Task Cancellation | 1 | 2 |
| LLM Cooldown | 1 | 1 |
| Release/ReleaseAll | 1 | 2 |
| Reproduction | 1 | 1 |
| Action Fields | 1 | 2 |
| **Total** | **6** | **10** |
