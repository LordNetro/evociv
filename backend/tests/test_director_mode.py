"""Tests for Director Mode — command queue, FSM interception, command dispatch,
LLM cancellation, thought injection, and WS dispatcher."""

import asyncio
import logging

import pytest

from app.simulation.world import World
from app.simulation.agent import Agent, MockLLMOrchestrator
from app.simulation.engine import SimulationEngine
from app.api.ws import command_dispatcher


# =============================================================================
# Helpers
# =============================================================================

def _make_engine(with_agent: bool = True) -> SimulationEngine:
    """Create a minimal engine with one agent."""
    world = World(width=10, height=10)
    agents = []
    if with_agent:
        agents.append(Agent(id="agent_001", name="TestBot", position=(5.0, 5.0)))
    engine = SimulationEngine(world=world, agents=agents)
    return engine


# =============================================================================
# 4.1 — Command Queue FSM Interception
# =============================================================================

class TestCommandQueueFSM:
    """Verify that the command queue check at the START of _fsm_evaluate()
    causes early return when a command is queued, and that normal FSM runs
    when the queue is empty or director_mode is off."""

    def test_early_return_when_command_queued(self):
        """Queued command causes early return — agent FSM does not advance."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")

        # Enqueue a move_to command
        cmd = {"type": "move_to", "payload": {"x": 3, "y": 3}}
        engine.director_mode = True
        engine.command_queue[agent.id] = cmd

        # Before evaluate: agent is still at (5, 5)
        assert agent.position == (5.0, 5.0)
        assert agent.target_position is None

        engine._run_agent_fsm(agent, tick=1)

        # After: command was consumed, agent should be moving toward (3, 3)
        assert agent.id not in engine.command_queue
        assert agent.target_position == (3.0, 3.0)
        assert agent.move_progress == 0.0
        assert len(agent.move_path) > 0
        assert agent.fsm_state == "moving"

    def test_normal_fsm_when_queue_empty(self):
        """Empty queue in director mode → normal FSM runs."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")
        engine.director_mode = True
        engine.command_queue.clear()

        # Normal FSM with no critical needs, no plan → should end up idle
        agent.hunger = 30
        agent.thirst = 30
        agent.energy = 80
        engine._run_agent_fsm(agent, tick=1)

        # Should NOT be moving from director command (no queued command)
        # Should have run normal FSM (could be idle, llm_trigger, etc.)
        assert agent.id not in engine.command_queue
        # Not moved to director command position
        assert agent.target_position is None

    def test_normal_fsm_when_director_mode_off(self):
        """director_mode = False → normal FSM even with stale queue entries."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")
        engine.director_mode = False

        # Place stale queue entry (should be ignored since director_mode is off)
        cmd = {"type": "move_to", "payload": {"x": 3, "y": 3}}
        engine.command_queue[agent.id] = cmd

        engine._run_agent_fsm(agent, tick=1)

        # Command should still be in queue (not consumed because director_mode=False)
        assert agent.id in engine.command_queue
        # FSM should have run normally (not from director command)
        assert len(agent.move_path) == 0 or agent.target_position is None

    def test_release_removes_single_agent_from_queue(self):
        """Release command removes only one agent's queue entry."""
        engine = _make_engine()
        agent1 = engine.agents[0]
        agent2 = Agent(id="agent_002", name="ExtraBot", position=(6.0, 6.0))
        engine.agents.append(agent2)
        engine.fsms[agent2.id] = type(engine.fsms[agent1.id])()

        engine.director_mode = True
        engine.command_queue["agent_001"] = {"type": "move_to", "payload": {"x": 0, "y": 0}}
        engine.command_queue["agent_002"] = {"type": "move_to", "payload": {"x": 9, "y": 9}}

        # Execute release for agent1
        fsm1 = engine.fsms[agent1.id]
        fsm1.transition_to("evaluate")
        engine.command_queue["agent_001"] = {"type": "release", "payload": {}}
        engine._run_agent_fsm(agent1, tick=1)

        # agent1's entry should be consumed (popped), agent2's should remain
        assert "agent_001" not in engine.command_queue
        assert "agent_002" in engine.command_queue

    def test_release_all_clears_queue_and_disables_director_mode(self):
        """release_all clears entire queue AND sets director_mode = False."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")

        engine.director_mode = True
        engine.command_queue[agent.id] = {"type": "release_all", "payload": {}}

        engine._run_agent_fsm(agent, tick=1)

        assert engine.command_queue == {}
        assert engine.director_mode is False

    def test_one_agent_command_does_not_affect_another(self):
        """One agent's queued command does not affect another's FSM."""
        engine = _make_engine()
        agent1 = engine.agents[0]
        agent2 = Agent(id="agent_002", name="OtherBot", position=(7.0, 7.0))
        engine.agents.append(agent2)
        engine.fsms[agent2.id] = type(engine.fsms[agent1.id])()

        engine.director_mode = True
        # Only agent1 has a command
        engine.command_queue["agent_001"] = {"type": "move_to", "payload": {"x": 0, "y": 0}}

        fsm1 = engine.fsms[agent1.id]
        fsm1.transition_to("evaluate")
        engine._run_agent_fsm(agent1, tick=1)
        assert agent1.fsm_state == "moving"

        # agent2 has no command → normal FSM (not director-mode-moving)
        fsm2 = engine.fsms[agent2.id]
        fsm2.transition_to("evaluate")
        engine._run_agent_fsm(agent2, tick=1)
        assert agent2.target_position is None  # not moved by director command


# =============================================================================
# 4.2 — Command Type Dispatch and LLM Cancellation
# =============================================================================

class TestCommandDispatch:
    """Verify each of the 6 command types produces correct side effects."""

    def test_move_to_sets_target_and_transitions(self):
        """move_to sets target_position, finds path, transitions to moving."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")

        engine.director_mode = True
        cmd = {"type": "move_to", "payload": {"x": 3, "y": 3}}
        engine.command_queue[agent.id] = cmd
        engine._run_agent_fsm(agent, tick=1)

        assert agent.target_position == (3.0, 3.0)
        assert agent.move_progress == 0.0
        assert len(agent.move_path) > 0
        assert agent.fsm_state == "moving"

    def test_do_action_sets_action_and_transitions(self):
        """do_action sets current_action and action_duration, transitions to executing."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")

        engine.director_mode = True
        cmd = {"type": "do_action", "payload": {"action_id": "gather"}}
        engine.command_queue[agent.id] = cmd
        engine._run_agent_fsm(agent, tick=1)

        assert agent.current_action == "gather"
        assert agent.action_progress == 0.0
        assert agent.action_duration > 0
        assert agent.fsm_state == "executing"

    def test_set_plan_sets_active_plan(self):
        """set_plan sets active_plan and resets plan_step_index."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")

        plan = {"steps": [{"action": "gather", "target": None, "reason": "Collect food"}]}
        engine.director_mode = True
        cmd = {"type": "set_plan", "payload": {"plan": plan}}
        engine.command_queue[agent.id] = cmd
        engine._run_agent_fsm(agent, tick=1)

        assert agent.active_plan == plan
        assert agent.plan_step_index == 0

    def test_inject_thought_appends_and_forces_llm_trigger(self):
        """inject_thought appends to injected_thoughts, sets last_thought, forces llm_trigger."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")

        engine.director_mode = True
        cmd = {"type": "inject_thought", "payload": {"text": "Go talk to Ena"}}
        engine.command_queue[agent.id] = cmd
        engine._run_agent_fsm(agent, tick=1)

        assert "Go talk to Ena" in agent.injected_thoughts
        assert agent.last_thought == "Go talk to Ena"
        assert agent.fsm_state == "llm_trigger"

    def test_release_does_not_change_fsm(self):
        """release pops from queue — no FSM transition, queue entry removed."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")

        engine.director_mode = True
        engine.command_queue[agent.id] = {"type": "release", "payload": {}}
        engine._run_agent_fsm(agent, tick=1)

        # release pops the entry; no FSM change, should fall through to normal FSM
        assert agent.id not in engine.command_queue
        # Since no command changed state, agent should continue normal FSM
        # (fsm_state won't be "moving" or "executing" from release)
        assert agent.current_action is None or agent.current_action == "idle"

    def test_release_all_clears_queue(self):
        """release_all clears queue and sets director_mode = False via _execute_director_command."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")

        engine.director_mode = True
        engine.command_queue["other_agent"] = {"type": "move_to", "payload": {"x": 1, "y": 1}}
        engine.command_queue[agent.id] = {"type": "release_all", "payload": {}}
        engine._run_agent_fsm(agent, tick=1)

        assert engine.command_queue == {}
        assert engine.director_mode is False

    def test_llm_future_cancelled_for_move_to(self):
        """move_to cancels pending LLM future."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = loop.create_future()
            agent.llm_future = future
            agent.llm_call_pending = True

            engine.director_mode = True
            cmd = {"type": "move_to", "payload": {"x": 3, "y": 3}}
            engine._execute_director_command(agent, cmd)

            assert future.cancelled() is True
            assert agent.llm_call_pending is False
        finally:
            loop.close()

    def test_llm_future_cancelled_for_do_action(self):
        """do_action cancels pending LLM future."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = loop.create_future()
            agent.llm_future = future
            agent.llm_call_pending = True

            cmd = {"type": "do_action", "payload": {"action_id": "rest"}}
            engine._execute_director_command(agent, cmd)

            assert future.cancelled() is True
            assert agent.llm_call_pending is False
        finally:
            loop.close()

    def test_llm_future_cancelled_for_set_plan(self):
        """set_plan cancels pending LLM future."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = loop.create_future()
            agent.llm_future = future
            agent.llm_call_pending = True

            plan = {"steps": [{"action": "gather", "target": None, "reason": "test"}]}
            cmd = {"type": "set_plan", "payload": {"plan": plan}}
            engine._execute_director_command(agent, cmd)

            assert future.cancelled() is True
            assert agent.llm_call_pending is False
        finally:
            loop.close()

    def test_llm_future_not_cancelled_for_inject_thought(self):
        """inject_thought does NOT cancel pending LLM future."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = loop.create_future()
            agent.llm_future = future
            agent.llm_call_pending = True

            cmd = {"type": "inject_thought", "payload": {"text": "Hello"}}
            engine._execute_director_command(agent, cmd)

            assert future.cancelled() is False
            assert agent.llm_call_pending is True  # still pending
        finally:
            loop.close()


# =============================================================================
# 4.3 — Thought Injection Pipeline
# =============================================================================

class TestThoughtInjection:
    """Verify that injected thoughts flow through build_prompt() correctly
    for both MockLLMOrchestrator and RealLLMOrchestrator."""

    def test_injected_thoughts_default_empty(self):
        """Agent starts with empty injected_thoughts."""
        agent = Agent(id="test", name="Test", position=(0.0, 0.0))
        assert agent.injected_thoughts == []

    def test_mock_build_prompt_includes_thought(self):
        """MockLLMOrchestrator.build_prompt prepends 'A voice in your head says: ...'."""
        orchestrator = MockLLMOrchestrator()
        agent = Agent(id="test", name="ThoughtBot", position=(0.0, 0.0))
        agent.injected_thoughts.append("Go talk to Ena")

        prompt = orchestrator.build_prompt(agent)

        assert "A voice in your head says: Go talk to Ena" in prompt

    def test_mock_build_prompt_multiple_thoughts(self):
        """Multiple injected thoughts each appear in the prompt."""
        orchestrator = MockLLMOrchestrator()
        agent = Agent(id="test", name="MultiBot", position=(0.0, 0.0))
        agent.injected_thoughts.append("First thought")
        agent.injected_thoughts.append("Second thought")

        prompt = orchestrator.build_prompt(agent)

        assert "A voice in your head says: First thought" in prompt
        assert "A voice in your head says: Second thought" in prompt

    def test_mock_build_prompt_adds_to_monologue_history(self):
        """Injected thoughts are appended to monologue_history after build_prompt."""
        orchestrator = MockLLMOrchestrator()
        agent = Agent(id="test", name="Historian", position=(0.0, 0.0))
        agent.injected_thoughts.append("Remember this")

        orchestrator.build_prompt(agent)

        assert "Remember this" in agent.monologue_history

    def test_mock_build_prompt_clears_injected_thoughts(self):
        """injected_thoughts is cleared after build_prompt processes them."""
        orchestrator = MockLLMOrchestrator()
        agent = Agent(id="test", name="ClearBot", position=(0.0, 0.0))
        agent.injected_thoughts.append("Will be cleared")

        orchestrator.build_prompt(agent)

        assert agent.injected_thoughts == []

    def test_mock_no_thoughts_no_change(self):
        """Empty injected_thoughts produces same prompt, no errors."""
        orchestrator = MockLLMOrchestrator()
        agent = Agent(id="test", name="QuietBot", position=(0.0, 0.0))

        prompt = orchestrator.build_prompt(agent)

        assert "A voice in your head says:" not in prompt
        assert agent.monologue_history == []
        assert agent.injected_thoughts == []


# =============================================================================
# 4.4 — FSM Non-Interference When Director Mode OFF
# =============================================================================

class TestNonInterference:
    """When director_mode = False, the engine behaves identically to
    pre-director-mode: zero behavioral change."""

    def test_agent_acts_normally_without_director_mode(self):
        """With director_mode=False (default), agent FSM works normally."""
        engine = _make_engine()
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")

        # Set up conditions for normal FSM: critical hunger + food nearby
        agent.hunger = 80
        agent.thirst = 30
        engine.world.get_tile(5, 5).resource_type = "berries"
        engine.world.get_tile(5, 5).amount = 5

        engine._run_agent_fsm(agent, tick=1)

        # Agent should have taken normal action (gather from survival chain)
        assert agent.current_action is not None

    def test_director_mode_flag_default_off(self):
        """SimulationEngine.director_mode defaults to False."""
        engine = _make_engine()
        assert engine.director_mode is False

    def test_command_queue_default_empty(self):
        """SimulationEngine.command_queue defaults to empty dict."""
        engine = _make_engine()
        assert engine.command_queue == {}

    def test_setting_director_mode_flag(self):
        """director_mode can be set to True."""
        engine = _make_engine()
        engine.director_mode = True
        assert engine.director_mode is True

    def test_engine_still_ticks_with_director_mode(self):
        """Engine tick loop still runs with director_mode=True."""
        engine = _make_engine()
        engine.director_mode = True
        # Agent should be able to move through FSM normally with no commands
        agent = engine.agents[0]
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")

        agent.hunger = 30
        agent.thirst = 30
        agent.energy = 80
        engine._run_agent_fsm(agent, tick=1)

        # FSM should have run (queue is empty, so no early return)
        assert agent.target_position is None


# =============================================================================
# 4.5 — WebSocket Command Dispatcher
# =============================================================================

class TestWSCommandDispatcher:
    """Verify command_dispatcher() correctly routes WS messages."""

    def test_valid_move_to_enqueued(self):
        """Valid move_to command is enqueued in engine.command_queue."""
        engine = _make_engine()
        engine.director_mode = True

        msg = {
            "type": "command",
            "payload": {
                "type": "move_to",
                "agent_id": "agent_001",
                "payload": {"x": 3, "y": 3}
            }
        }
        command_dispatcher(msg, engine)

        assert "agent_001" in engine.command_queue
        assert engine.command_queue["agent_001"]["type"] == "move_to"
        assert engine.command_queue["agent_001"]["payload"] == {"x": 3, "y": 3}

    def test_valid_do_action_enqueued(self):
        """Valid do_action command is enqueued."""
        engine = _make_engine()
        engine.director_mode = True

        msg = {
            "type": "command",
            "payload": {
                "type": "do_action",
                "agent_id": "agent_001",
                "payload": {"action_id": "gather"}
            }
        }
        command_dispatcher(msg, engine)

        assert "agent_001" in engine.command_queue
        assert engine.command_queue["agent_001"]["type"] == "do_action"

    def test_valid_inject_thought_enqueued(self):
        """Valid inject_thought command is enqueued."""
        engine = _make_engine()
        engine.director_mode = True

        msg = {
            "type": "command",
            "payload": {
                "type": "inject_thought",
                "agent_id": "agent_001",
                "payload": {"text": "Hello there"}
            }
        }
        command_dispatcher(msg, engine)

        assert engine.command_queue["agent_001"]["type"] == "inject_thought"
        assert engine.command_queue["agent_001"]["payload"]["text"] == "Hello there"

    def test_release_all_clears_queue_and_disables_director_mode(self):
        """release_all command clears queue and sets director_mode = False."""
        engine = _make_engine()
        engine.director_mode = True
        engine.command_queue["agent_001"] = {"type": "move_to", "payload": {}}

        msg = {
            "type": "command",
            "payload": {
                "type": "release_all",
                "agent_id": "",
                "payload": {}
            }
        }
        command_dispatcher(msg, engine)

        assert engine.command_queue == {}
        assert engine.director_mode is False

    def test_invalid_command_type_logs_warning(self, caplog):
        """Unknown command type logs WARNING without crashing."""
        engine = _make_engine()

        msg = {
            "type": "command",
            "payload": {
                "type": "fly_to_the_moon",
                "agent_id": "agent_001",
                "payload": {}
            }
        }
        with caplog.at_level(logging.WARNING):
            command_dispatcher(msg, engine)

        assert "Unknown command type" in caplog.text
        assert engine.command_queue == {}

    def test_release_sets_director_mode(self):
        """release command enqueues correctly without changing director_mode."""
        engine = _make_engine()
        engine.director_mode = True
        engine.command_queue["agent_001"] = {"type": "move_to", "payload": {"x": 1, "y": 1}}

        msg = {
            "type": "command",
            "payload": {
                "type": "release",
                "agent_id": "agent_001",
                "payload": {}
            }
        }
        command_dispatcher(msg, engine)

        # release replaces the existing command in the queue
        assert engine.command_queue["agent_001"]["type"] == "release"
        # director_mode should still be True (only release_all changes it)
        assert engine.director_mode is True

    def test_unknown_agent_id_logs_warning(self, caplog):
        """Unknown agent_id logs WARNING without crashing."""
        engine = _make_engine()

        msg = {
            "type": "command",
            "payload": {
                "type": "move_to",
                "agent_id": "nonexistent_agent",
                "payload": {"x": 1, "y": 1}
            }
        }
        with caplog.at_level(logging.WARNING):
            command_dispatcher(msg, engine)

        assert "Unknown agent_id" in caplog.text
        assert "nonexistent_agent" in caplog.text
        assert engine.command_queue == {}

    def test_empty_agent_id_logs_warning(self, caplog):
        """Missing agent_id logs WARNING without crashing."""
        engine = _make_engine()

        msg = {
            "type": "command",
            "payload": {
                "type": "move_to",
                "agent_id": "",
                "payload": {"x": 1, "y": 1}
            }
        }
        with caplog.at_level(logging.WARNING):
            command_dispatcher(msg, engine)

        assert "command missing agent_id" in caplog.text
        assert engine.command_queue == {}

    def test_set_plan_enqueued(self):
        """set_plan command is enqueued with plan payload."""
        engine = _make_engine()
        engine.director_mode = True

        plan = {"steps": [{"action": "gather", "target": None, "reason": "test"}]}
        msg = {
            "type": "command",
            "payload": {
                "type": "set_plan",
                "agent_id": "agent_001",
                "payload": {"plan": plan}
            }
        }
        command_dispatcher(msg, engine)

        assert engine.command_queue["agent_001"]["type"] == "set_plan"
        assert engine.command_queue["agent_001"]["payload"]["plan"] == plan


# =============================================================================
# 4.3 — F2 Task Cancellation Verification
# =============================================================================

class TestF2TaskCancellation:
    """Verify background tasks are cancelled alongside futures."""

    @pytest.mark.anyio
    async def test_call_async_cancels_task_via_engine_command(self):
        """call_async creates tracked task; engine command cancels both future and task."""
        world = World(width=10, height=10)
        agent = Agent(id="agent_001", name="TestBot", position=(5.0, 5.0))
        engine = SimulationEngine(world=world, agents=[agent])
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")
        # Make an LLM call via orchestrator
        prompt = "test prompt"
        future = engine.llm.call_async(agent.id, prompt)
        agent.llm_future = future
        agent.llm_call_pending = True
        # Verify background task is tracked
        assert agent.id in engine.llm._pending_tasks
        task = engine.llm._pending_tasks[agent.id]
        assert not task.done()
        # Now cancel via a director command
        cmd = {"type": "move_to", "payload": {"x": 3, "y": 3}}
        engine._execute_director_command(agent, cmd)
        # Future should be cancelled
        assert future.cancelled()
        assert agent.llm_call_pending is False
        # Background task should have been removed from tracking
        assert agent.id not in engine.llm._pending_tasks
        # Yield to event loop to let cancellation propagate
        await asyncio.sleep(0)
        assert task.cancelled()

    @pytest.mark.anyio
    async def test_inject_thought_does_not_cancel_task(self):
        """inject_thought does NOT cancel future or background task."""
        world = World(width=10, height=10)
        agent = Agent(id="agent_001", name="TestBot", position=(5.0, 5.0))
        engine = SimulationEngine(world=world, agents=[agent])
        fsm = engine.fsms[agent.id]
        fsm.transition_to("evaluate")
        prompt = "test prompt"
        future = engine.llm.call_async(agent.id, prompt)
        agent.llm_future = future
        agent.llm_call_pending = True
        assert agent.id in engine.llm._pending_tasks
        # inject_thought should not cancel
        cmd = {"type": "inject_thought", "payload": {"text": "Hello"}}
        engine._execute_director_command(agent, cmd)
        assert not future.cancelled()
        assert agent.id in engine.llm._pending_tasks  # task still tracked


# =============================================================================
# 4.4 — F5+F7: Complete release/reset
# =============================================================================

class TestF5F7ReleaseReset:
    """Verify release/release_all reset all agent state fields."""

    def _set_agent_busy_state(self, agent: Agent) -> None:
        """Set an agent up with active plans, actions, LLM pending, etc."""
        agent.active_plan = {"steps": [{"action": "gather"}]}
        agent.plan_step_index = 0
        agent.current_action = "gather"
        agent.current_action_emoji = "🫐"
        agent.action_duration = 5
        agent.action_progress = 0.5
        agent.target_position = (10.0, 10.0)
        agent.move_path = [(6, 6), (7, 7)]
        agent.move_progress = 0.3
        agent.injected_thoughts = ["Do something"]
        agent._last_llm_tick = 100
        agent.llm_call_pending = True
        agent.llm_future = asyncio.new_event_loop().create_future()
        # Close the loop to prevent warnings
        agent.llm_future.cancel()

    def test_release_all_full_reset(self):
        """release_all clears ALL state for ALL agents and resets director mode."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a2 = Agent(id="a2", name="Bob", position=(6.0, 6.0))
        engine = SimulationEngine(world=world, agents=[a1, a2])
        engine.director_mode = True
        engine.command_queue["a1"] = {"type": "move_to", "payload": {}}
        engine.command_queue["a2"] = {"type": "do_action", "payload": {}}
        self._set_agent_busy_state(a1)
        self._set_agent_busy_state(a2)
        # Execute release_all (must be through a valid agent's command queue)
        fsm = engine.fsms[a1.id]
        fsm.transition_to("evaluate")
        engine.command_queue["a1"] = {"type": "release_all", "payload": {}}
        engine._run_agent_fsm(a1, tick=1)
        # Verify ALL state cleared for ALL agents
        for agent in [a1, a2]:
            assert agent.active_plan is None, f"{agent.id}: active_plan not None"
            assert agent.plan_step_index == 0, f"{agent.id}: plan_step_index not 0"
            assert agent.current_action is None, f"{agent.id}: current_action not None"
            assert agent.current_action_emoji == "", f"{agent.id}: emoji not cleared"
            assert agent.action_duration == 0, f"{agent.id}: duration not 0"
            assert agent.action_progress == 0.0, f"{agent.id}: progress not 0.0"
            assert agent.target_position is None, f"{agent.id}: target_position not None"
            assert agent.move_path is None or agent.move_path == [], f"{agent.id}: move_path not cleared"
            assert agent.injected_thoughts == [], f"{agent.id}: injected_thoughts not cleared"
            assert agent._last_llm_tick == -999, f"{agent.id}: _last_llm_tick not reset"
            assert agent.llm_call_pending is False, f"{agent.id}: llm_call_pending not False"
            assert agent.llm_future is None, f"{agent.id}: llm_future not None"
        assert engine.director_mode is False
        assert engine.command_queue == {}

    def test_release_single_agent_full_reset(self):
        """release clears ALL state for one agent."""
        world = World(width=10, height=10)
        a1 = Agent(id="a1", name="Alice", position=(5.0, 5.0))
        a2 = Agent(id="a2", name="Bob", position=(6.0, 6.0))
        engine = SimulationEngine(world=world, agents=[a1, a2])
        engine.director_mode = True
        self._set_agent_busy_state(a1)
        self._set_agent_busy_state(a2)
        # Release a1 only
        fsm = engine.fsms[a1.id]
        fsm.transition_to("evaluate")
        engine.command_queue["a1"] = {"type": "release", "payload": {}}
        engine._run_agent_fsm(a1, tick=1)
        # a1 should be fully cleared
        assert a1.active_plan is None
        assert a1.current_action is None
        assert a1.current_action_emoji == ""
        assert a1.action_duration == 0
        assert a1.action_progress == 0.0
        assert a1.target_position is None
        assert a1.move_path is None or a1.move_path == []
        assert a1.injected_thoughts == []
        assert a1._last_llm_tick == -999
        assert a1.llm_call_pending is False
        assert a1.llm_future is None
        # a2 should still have its state
        assert a2.current_action == "gather"
        assert a2.llm_call_pending is True
        # director_mode should still be True (only release_all disables it)
        assert engine.director_mode is True
