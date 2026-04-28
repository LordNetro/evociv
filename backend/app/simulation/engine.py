"""Simulation engine — async tick loop orchestrator."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from app.core.config import settings
from app.simulation.agent import Agent, FSM
from app.simulation.actions import (
    ActionType,
    REGISTRY,
    get_action_duration,
    ACTION_EMOJIS,
)
from app.simulation.event_queue import (
    EventQueue,
    check_proximity_encounters,
    check_resource_discoveries,
    create_death_event,
)
from app.simulation.snapshot import WorldSnapshotBuilder
from app.simulation.world import World

logger = logging.getLogger("evociv.engine")
logger.setLevel(logging.WARNING)

# Constants
HUNGER_DECAY = 0.1        # per tick
THIRST_DECAY = 0.15       # per tick
ENERGY_DECAY = 0.05       # per tick
CRITICAL_THRESHOLD = 15   # % below which agent seeks resource
INTERACTION_RADIUS = 3.0  # tiles


class SimulationEngine:
    def __init__(
        self,
        world: World,
        agents: list[Agent],
        ws_manager=None,
        db_session_factory=None,
        llm_orchestrator=None,
    ):
        self.world = world
        self.agents = agents
        self.ws_manager = ws_manager
        self.db_session_factory = db_session_factory

        self.tick_count = 0
        self.running = False
        self._paused = asyncio.Event()
        self._paused.set()  # Not paused by default
        self._tick_task: Optional[asyncio.Task] = None

        # Subsystems
        self.fsms = {agent.id: FSM() for agent in agents}  # One FSM per agent
        self.event_queue = EventQueue()

        # LLM orchestrator: use injected one, or create mock as fallback
        if llm_orchestrator is not None:
            self.llm = llm_orchestrator
        else:
            from app.simulation.agent import MockLLMOrchestrator
            self.llm = MockLLMOrchestrator()

        self.builder = WorldSnapshotBuilder(world, agents)

        # State tracking
        self._discovered_set: set[tuple[str, int, int]] = set()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self.running = True
        self._tick_task = asyncio.create_task(
            self._tick_loop(), name="simulation-loop"
        )
        logger.info("Engine started")

    async def stop(self) -> None:
        self.running = False
        self._paused.set()  # Unblock if paused
        if self._tick_task:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
            self._tick_task = None
        logger.info("Engine stopped")

    def pause(self) -> None:
        self._paused.clear()
        logger.info("Engine paused")

    def resume(self) -> None:
        self._paused.set()
        logger.info("Engine resumed")

    @property
    def is_paused(self) -> bool:
        return not self._paused.is_set()

    # ------------------------------------------------------------------
    # Tick loop
    # ------------------------------------------------------------------

    async def _tick_loop(self) -> None:
        tick_interval = settings.tick_rate  # e.g., 0.1 s (10 ticks/sec)
        while self.running:
            await self._paused.wait()  # Blocks if paused

            tick_start = time.monotonic()

            try:
                await self._tick()
            except Exception as e:
                logger.exception(f"Error in tick {self.tick_count}: {e}")

            elapsed = time.monotonic() - tick_start
            sleep_time = max(0, tick_interval - elapsed)
            if elapsed > tick_interval:
                logger.warning(
                    f"Tick {self.tick_count} took {elapsed * 1000:.0f}ms "
                    f"(slower than {tick_interval * 1000:.0f}ms interval)"
                )
            await asyncio.sleep(sleep_time)

    # ------------------------------------------------------------------
    # Main tick
    # ------------------------------------------------------------------

    async def _tick(self) -> None:
        self.tick_count += 1
        tick = self.tick_count

        # 1. Decay physical needs and check death
        await self._process_needs(tick)

        # 2. Run FSM for each agent
        for agent in list(self.agents):  # Copy in case agents die mid-iteration
            try:
                self._run_agent_fsm(agent, tick)
            except Exception as e:
                logger.error(f"FSM error for {agent.name}: {e}")

        # 3. Process event queue (events pushed during FSM run)
        events = self.event_queue.drain()

        # 4. Poll LLM futures
        self._poll_llm_responses(tick)

        # 5. World regeneration
        self.world.regenerate_resources()

        # 6. Proximity checks
        proximity_events = check_proximity_encounters(
            self.agents, INTERACTION_RADIUS, tick
        )
        for ev in proximity_events:
            self.event_queue.push(
                ev.type,
                ev.description,
                ev.severity,
                ev.agent_ids,
                tick,
                ev.position,
            )

        # 7. Resource discovery checks
        for agent in self.agents:
            discovery_events = check_resource_discoveries(
                agent, self.world, self._discovered_set, tick
            )
            for ev in discovery_events:
                self.event_queue.push(
                    ev.type,
                    ev.description,
                    ev.severity,
                    ev.agent_ids,
                    tick,
                    ev.position,
                )

        # 8. Collect all events
        all_events = events + self.event_queue.drain()

        # 9. Build and broadcast snapshot
        snapshot = self.builder.build_delta(tick, all_events)
        if self.ws_manager:
            try:
                await self.ws_manager.broadcast(
                    {
                        "type": "snapshot",
                        "payload": snapshot.model_dump(),
                    }
                )
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

        # 10. Log to SQLite (fire and forget)
        if self.db_session_factory:
            asyncio.create_task(self._log_to_db(tick, snapshot, all_events))

    # ------------------------------------------------------------------
    # Needs & death
    # ------------------------------------------------------------------

    async def _process_needs(self, tick: int) -> None:
        """Decay hunger/thirst/energy and check for deaths."""
        dead_agents: list[Agent] = []
        for agent in self.agents:
            agent.hunger = min(100.0, agent.hunger + HUNGER_DECAY)
            agent.thirst = min(100.0, agent.thirst + THIRST_DECAY)
            agent.energy = max(0.0, agent.energy - ENERGY_DECAY)

            # Starvation / dehydration damage
            if agent.hunger >= 100:
                agent.health -= 0.5
            if agent.thirst >= 100:
                agent.health -= 1.0

            # Clamp to [0, 100]
            agent.hunger = max(0.0, min(100.0, agent.hunger))
            agent.thirst = max(0.0, min(100.0, agent.thirst))
            agent.health = max(0.0, min(100.0, agent.health))
            agent.energy = max(0.0, min(100.0, agent.energy))

            if agent.health <= 0:
                dead_agents.append(agent)

        for agent in dead_agents:
            death_event = create_death_event(agent, tick)
            self.event_queue.push(
                death_event.type,
                death_event.description,
                death_event.severity,
                death_event.agent_ids,
                tick,
            )
            self.agents.remove(agent)
            self.builder.mark_agent_removed(agent.id)
            logger.warning(f"{agent.name} died at tick {tick}")

    # ------------------------------------------------------------------
    # FSM runner
    # ------------------------------------------------------------------

    def _run_agent_fsm(self, agent: Agent, tick: int) -> None:
        """Execute one tick of the agent's FSM."""
        fsm = self.fsms[agent.id]

        # Keep agent.fsm_state in sync for snapshot building
        agent.fsm_state = fsm.current_state

        match fsm.current_state:
            case "idle":
                self._fsm_idle(agent, fsm, tick)
            case "evaluate":
                self._fsm_evaluate(agent, fsm, tick)
            case "moving":
                self._fsm_moving(agent, fsm, tick)
            case "executing":
                self._fsm_executing(agent, fsm, tick)
            case "llm_trigger":
                self._fsm_llm_trigger(agent, fsm, tick)
            case "llm_waiting":
                self._fsm_llm_waiting(agent, fsm, tick)

        # Sync again after potential transition
        agent.fsm_state = fsm.current_state

    def _fsm_idle(self, agent: Agent, fsm: FSM, tick: int) -> None:
        """IDLE → always evaluate needs."""
        fsm.transition_to("evaluate")

    def _fsm_evaluate(self, agent: Agent, fsm: FSM, tick: int) -> None:
        """Check needs and decide next state."""
        # Critical needs → handle with FSM instinct
        if agent.hunger > 90 or agent.thirst > 90:
            nearby = self.world.get_nearby_resources(agent.position, radius=8)
            food_nearby = [r for r in nearby if r[2] in ("berries", "tree")]
            water_nearby = [r for r in nearby if r[2] == "water"]

            if agent.thirst > agent.hunger and water_nearby:
                target = (water_nearby[0][0], water_nearby[0][1])
                agent.current_action = "seeking water"
                agent.current_action_emoji = "💧"
                agent.target_position = (float(target[0]), float(target[1]))
                agent.move_path = self.world.find_path(
                    (int(agent.position[0]), int(agent.position[1])), target
                )
                agent.move_progress = 0.0
                fsm.transition_to("moving")
                return
            elif food_nearby:
                target = (food_nearby[0][0], food_nearby[0][1])
                agent.current_action = "seeking food"
                agent.current_action_emoji = "🍎"
                agent.target_position = (float(target[0]), float(target[1]))
                agent.move_path = self.world.find_path(
                    (int(agent.position[0]), int(agent.position[1])), target
                )
                agent.move_progress = 0.0
                fsm.transition_to("moving")
                return

        # Needs met → try LLM for higher-level planning
        if not agent.active_plan and not agent.llm_call_pending:
            fsm.transition_to("llm_trigger")
        elif agent.active_plan:
            # Continue with existing plan
            step = agent.active_plan["steps"][agent.plan_step_index]
            action_type = ActionType(step["action"])
            agent.current_action = step["action"]
            agent.current_action_emoji = ACTION_EMOJIS.get(action_type, "❓")
            duration = get_action_duration(action_type, agent)
            agent.action_duration = duration
            agent.action_progress = 0.0

            # Set target if provided by the plan step
            target = step.get("target")
            if target is not None:
                agent.target_position = (float(target[0]), float(target[1]))

            if action_type == ActionType.MOVE:
                # Pre-compute path for movement
                start = (int(agent.position[0]), int(agent.position[1]))
                end = (int(agent.target_position[0]), int(agent.target_position[1]))
                agent.move_path = self.world.find_path(start, end)
                agent.move_progress = 0.0
                fsm.transition_to("moving")
            else:
                fsm.transition_to("executing")
        else:
            # No plan, no LLM pending, no critical need → wait
            agent.current_action = "idle"
            agent.current_action_emoji = "💤"
            fsm.transition_to("idle")

    def _fsm_moving(self, agent: Agent, fsm: FSM, tick: int) -> None:
        """Advance along path toward target."""
        if not agent.move_path:
            # No path → recalculate or skip
            if agent.target_position:
                start = (int(agent.position[0]), int(agent.position[1]))
                end = (int(agent.target_position[0]), int(agent.target_position[1]))
                agent.move_path = self.world.find_path(start, end)
            if not agent.move_path:
                fsm.transition_to("evaluate")
                return

        # Check for critical need interruption
        if agent.hunger > 95 or agent.thirst > 95:
            fsm.transition_to("evaluate")
            return

        # Advance one step along path
        next_pos = agent.move_path.pop(0)
        agent.position = (float(next_pos[0]), float(next_pos[1]))
        self.builder.mark_agent_dirty(agent.id)

        # Check for resource discovery
        discovery_events = check_resource_discoveries(
            agent, self.world, self._discovered_set, tick
        )
        for ev in discovery_events:
            self.event_queue.push(
                ev.type,
                ev.description,
                ev.severity,
                ev.agent_ids,
                tick,
                ev.position,
            )

        if not agent.move_path:
            # Arrived at destination
            fsm.transition_to("evaluate")

    def _fsm_executing(self, agent: Agent, fsm: FSM, tick: int) -> None:
        """Execute current action, advancing progress each tick."""
        if not agent.current_action:
            fsm.transition_to("evaluate")
            return

        agent.action_progress += 1.0
        self.builder.mark_agent_dirty(agent.id)

        if agent.action_progress >= agent.action_duration:
            # Action complete — apply effects
            try:
                action_type = ActionType(agent.current_action)
            except ValueError:
                # Unknown action string
                logger.warning(
                    f"Unknown action '{agent.current_action}' for {agent.name}"
                )
                fsm.transition_to("evaluate")
                return

            handler = REGISTRY.get(action_type)
            if handler:
                target = None
                if agent.target_position:
                    target = (
                        int(agent.target_position[0]),
                        int(agent.target_position[1]),
                    )
                result = handler(agent, self.world, target, None)

                if result.interrupted or not result.success:
                    fsm.transition_to("evaluate")
                    return

            # Advance plan
            agent.action_progress = 0.0
            agent.action_duration = 0
            agent.current_action = None

            if agent.active_plan:
                agent.plan_step_index += 1
                if agent.plan_step_index >= len(agent.active_plan["steps"]):
                    # Plan complete
                    agent.active_plan = None
                    agent.plan_step_index = 0
                fsm.transition_to("evaluate")
            else:
                fsm.transition_to("evaluate")

    def _fsm_llm_trigger(self, agent: Agent, fsm: FSM, tick: int) -> None:
        """Queue an async LLM call."""
        if agent.llm_call_pending:
            fsm.transition_to("llm_waiting")
            return

        # Cooldown: don't retry LLM more than once every 15 ticks
        last = getattr(agent, '_last_llm_tick', 0)
        if tick - last < 15:
            agent.last_thought = "(waiting before retrying)"
            fsm.transition_to("llm_waiting")
            return

        prompt = self.llm.build_prompt(agent, self.world)
        agent.llm_future = self.llm.call_async(agent.id, prompt)
        agent.llm_call_pending = True
        agent._last_llm_tick = tick
        agent.last_thought = "Thinking about what to do next..."
        self.builder.mark_agent_dirty(agent.id)
        fsm.transition_to("llm_waiting")

    def _fsm_llm_waiting(self, agent: Agent, fsm: FSM, tick: int) -> None:
        """Wait for LLM response while acting on instinct."""
        if agent.llm_future and agent.llm_future.done():
            try:
                result = agent.llm_future.result()
                if result.get("success") and result.get("data"):
                    plan = result["data"]
                    agent.active_plan = plan
                    agent.plan_step_index = 0
                    agent.last_thought = plan.get(
                        "reasoning", ""
                    ) or plan.get("think_aloud", "")
                    agent.monologue_history.append(agent.last_thought)
                    if len(agent.monologue_history) > 10:
                        agent.monologue_history.pop(0)
                    logger.debug(
                        f"{agent.name} received new plan: "
                        f"{plan.get('intention', '')}"
                    )
                else:
                    err = result.get('error', 'unknown')
                    logger.warning(f"{agent.name} LLM call failed: [{err}] (result keys: {list(result.keys())})")
                    agent.last_thought = f"Plan failed: {err}"
            except Exception as e:
                logger.error(f"{agent.name} LLM future error: {e}")

            agent.llm_call_pending = False
            agent.llm_future = None
            self.builder.mark_agent_dirty(agent.id)
            fsm.transition_to("evaluate")
        else:
            # Still waiting — act on instinct: move toward nearest resource
            agent.last_thought = "Waiting for guidance..."
            agent.current_action = "waiting"
            agent.current_action_emoji = "⏳"
            self.builder.mark_agent_dirty(agent.id)

            if agent.hunger > 80 or agent.thirst > 80:
                nearby = self.world.get_nearby_resources(agent.position, radius=5)
                target = None
                for r in nearby:
                    if r[2] in ("berries", "water") and r[3] > 0:
                        target = (r[0], r[1])
                        break
                if target and not agent.move_path:
                    start = (int(agent.position[0]), int(agent.position[1]))
                    agent.move_path = self.world.find_path(start, target)

    # ------------------------------------------------------------------
    # LLM polling
    # ------------------------------------------------------------------

    def _poll_llm_responses(self, tick: int) -> None:
        """Check for completed LLM futures and update agent plans."""
        completed = self.llm.poll_completed()
        for agent_id, response in completed:
            agent = next((a for a in self.agents if a.id == agent_id), None)
            if not agent or not agent.llm_call_pending:
                # Already handled by _fsm_llm_waiting or agent removed
                continue

            if response.get("success") and response.get("data"):
                plan = response["data"]
                agent.active_plan = plan
                agent.plan_step_index = 0
                agent.last_thought = plan.get("think_aloud") or plan.get(
                    "reasoning", ""
                )
                agent.monologue_history.append(agent.last_thought)
                if len(agent.monologue_history) > 10:
                    agent.monologue_history.pop(0)
                agent.llm_call_pending = False
                agent.llm_future = None
                self.builder.mark_agent_dirty(agent.id)
                logger.debug(
                    f"{agent.name} plan updated via poll: "
                    f"{plan.get('intention', '')}"
                )

    # ------------------------------------------------------------------
    # DB logging
    # ------------------------------------------------------------------

    async def _log_to_db(self, tick: int, snapshot, events: list) -> None:
        """Async SQLite logging — errors never crash the engine."""
        if not self.db_session_factory:
            return
        try:
            async with self.db_session_factory() as session:
                from sqlalchemy import select
                from app.db.models import TickMetric as TickMetricModel
                from app.db.models import SimEvent as SimEventModel

                # Upsert tick_metrics (tick is unique, may already exist from previous run)
                existing = await session.execute(
                    select(TickMetricModel).where(TickMetricModel.tick == tick)
                )
                metrics = existing.scalar_one_or_none()
                if metrics:
                    metrics.population = snapshot.metrics.population
                    metrics.avg_hunger = snapshot.metrics.avg_hunger
                    metrics.avg_thirst = snapshot.metrics.avg_thirst
                    metrics.avg_health = snapshot.metrics.avg_health
                    metrics.avg_energy = snapshot.metrics.avg_energy
                else:
                    session.add(TickMetricModel(
                        tick=tick,
                        population=snapshot.metrics.population,
                        avg_hunger=snapshot.metrics.avg_hunger,
                        avg_thirst=snapshot.metrics.avg_thirst,
                        avg_health=snapshot.metrics.avg_health,
                        avg_energy=snapshot.metrics.avg_energy,
                    ))

                for event in events:
                    session.add(SimEventModel(
                        tick=tick,
                        agent_id=event.agent_ids[0] if event.agent_ids else "",
                        event_type=event.type,
                        description=event.description,
                    ))

                await session.commit()
        except Exception as e:
            logger.error(f"DB logging error (tick {tick}): {e}")


__all__ = ["SimulationEngine"]
