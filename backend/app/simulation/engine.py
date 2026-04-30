"""Simulation engine — async tick loop orchestrator."""

from __future__ import annotations

import asyncio
import logging
import math
import time
import uuid
from typing import Optional

from app.core.config import settings
from app.simulation.agent import Agent, FSM, RelationshipData
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
from app.simulation.conversation import ConversationManager
from app.simulation.faction import FactionManager
from app.simulation.colony import ColonyStatsCollector
from app.simulation.conversation import Message
from app.simulation import roles as roles_module

logger = logging.getLogger("evociv.engine")
logger.setLevel(logging.INFO)

# Constants
HUNGER_DECAY = 0.04        # per tick
THIRST_DECAY = 0.06       # per tick
ENERGY_DECAY = 0.03       # per tick
CRITICAL_HUNGER = 70       # hunger above this triggers instinct food seeking
CRITICAL_THIRST = 70       # thirst above this triggers instinct water seeking
CRITICAL_LLM_TRIGGER = 85  # only LLM trigger on critical (for higher-level plans)
INTERACTION_RADIUS = 3.0  # tiles
REPRODUCTION_COOLDOWN = 500  # ticks between reproductions
MAX_POPULATION = 20
INTERACTION_THRESHOLD = 5
DECAY_INTERVAL = 100


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
        self.conversation_manager = ConversationManager()
        self.faction_manager = FactionManager()
        self.colony_stats_collector = ColonyStatsCollector()

        # LLM orchestrator: use injected one, or create mock as fallback
        if llm_orchestrator is not None:
            self.llm = llm_orchestrator
        else:
            from app.simulation.agent import MockLLMOrchestrator
            self.llm = MockLLMOrchestrator()

        self.builder = WorldSnapshotBuilder(world, agents)
        self._latest_full_snapshot: Optional[dict] = None

        # Background task tracking
        self._background_tasks: set[asyncio.Task] = set()

        # State tracking
        self._discovered_set: set[tuple[str, int, int]] = set()
        self._agent_health: dict[str, float] = {a.id: a.health for a in agents}

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
        # Cancel background tasks
        for task in list(self._background_tasks):
            task.cancel()
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

    @property
    def latest_snapshot(self) -> Optional[dict]:
        return self._latest_full_snapshot

    def add_agent(self, agent: Agent) -> str:
        """Add a new agent to the simulation. Returns the agent ID."""
        # Apply role stats and role_data if not already set
        if not agent.role_data:
            roles_module.apply_role_stats(agent)
        # Assign to a faction if not already assigned (before append so index is correct)
        if not agent.faction_id:
            factions = self.faction_manager.list_all()
            if factions:
                # Distribute round-robin
                idx = len(self.agents) % len(factions)
                faction = factions[idx]
                agent.faction_id = faction.id
                self.faction_manager.join(agent.id, faction.id)
        self.agents.append(agent)
        self.fsms[agent.id] = FSM()
        self._agent_health[agent.id] = agent.health
        self.builder.mark_agent_dirty(agent.id)
        # Inject faction_manager into LLM orchestrator if needed
        if hasattr(self.llm, "faction_manager") and getattr(self.llm, "faction_manager", None) is None:
            self.llm.faction_manager = self.faction_manager
        self.colony_stats_collector.record_birth()
        logger.info(f"Agent {agent.name} ({agent.id}) added to simulation")
        return agent.id

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

        # 1b. Update storage proximity flags
        for agent in self.agents:
            ax, ay = int(agent.position[0]), int(agent.position[1])
            agent._storage_nearby = False
            for struct in self.world.structures.list_all():
                if struct.structure_type == "storage_hut":
                    sx, sy = struct.position
                    if max(abs(sx - ax), abs(sy - ay)) <= 3:
                        agent._storage_nearby = True
                        break

        # 2. Run FSM for each agent
        for agent in list(self.agents):  # Copy in case agents die mid-iteration
            try:
                self._run_agent_fsm(agent, tick)
            except Exception as e:
                logger.error(f"FSM error for {agent.name}: {e}")

        # 3. Process social interactions (conversations)
        social_events = self.conversation_manager.detect_encounters(
            self.agents, INTERACTION_RADIUS, tick
        )
        for ev in social_events:
            self.event_queue.push(
                ev.type,
                ev.description,
                ev.severity,
                ev.agent_ids,
                tick,
                ev.position,
            )
            # F6: update relationships for socialize and knowledge share events
            if ev.type in ("socialize", "knowledge_shared") and len(ev.agent_ids) == 2:
                a1 = next((a for a in self.agents if a.id == ev.agent_ids[0]), None)
                a2 = next((a for a in self.agents if a.id == ev.agent_ids[1]), None)
                if a1 and a2:
                    self._update_relationship(a1, a2, tick, score_delta=0.1)

        # 3b. Process pending trade proposals
        await self._process_trade_proposals(tick)

        # 4. Process event queue (events pushed during FSM run)
        events = self.event_queue.drain()

        # 4. Poll LLM futures
        self._poll_llm_responses(tick)

        # 5. World regeneration
        self.world.regenerate_resources()

        # 5b. Structure farm bonuses
        self.world.structures.tick_farms(self.agents)

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
        colony_stats = self.colony_stats_collector.collect(
            self.agents, self.faction_manager
        )
        colony_stats_dict = {
            "population": colony_stats.population,
            "births": colony_stats.births,
            "deaths": colony_stats.deaths,
            "total_resources": colony_stats.total_resources,
        }
        snapshot = self.builder.build_delta(
            tick, all_events, faction_manager=self.faction_manager, colony_stats=colony_stats_dict
        )
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

        # 10. Store full snapshot for new WS clients
        self._latest_full_snapshot = self.builder.build(
            tick, all_events, faction_manager=self.faction_manager, colony_stats=colony_stats_dict
        ).model_dump()
        if self.ws_manager:
            self.ws_manager.latest_snapshot = self._latest_full_snapshot

        # 11. Log to SQLite (fire and forget)
        if self.db_session_factory:
            task = asyncio.create_task(self._log_to_db(tick, snapshot, all_events))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    # ------------------------------------------------------------------
    # Needs & death
    # ------------------------------------------------------------------

    def _process_say_to(self, agent: Agent, response_data: dict, tick: int) -> None:
        """Process say_to / think_aloud from LLM response and emit dialogue events."""
        say_to = response_data.get("say_to")
        think_aloud = response_data.get("think_aloud")

        if say_to and say_to.get("agent_id") and say_to.get("text"):
            agent.current_dialogue = say_to["text"]
            agent.dialogue_type = "speech"
            target = next((a for a in self.agents if a.id == say_to["agent_id"]), None)
            if target:
                target.conversation_queue.append(
                    Message(
                        sender_id=agent.id,
                        content={"type": "dialogue", "text": say_to["text"]},
                        tick=tick,
                    )
                )
                self._update_relationship(agent, target, tick, score_delta=0.05)
                self.event_queue.push(
                    "dialogue",
                    f"{agent.name} → {target.name}: {say_to['text']}",
                    "info",
                    [agent.id, target.id],
                    tick,
                    agent.position,
                )
            else:
                logger.warning(f"say_to target {say_to['agent_id']} not found for {agent.name}")
                self.event_queue.push(
                    "dialogue",
                    f"{agent.name} → ??? : {say_to['text']}",
                    "info",
                    [agent.id],
                    tick,
                    agent.position,
                )
        elif think_aloud and str(think_aloud).strip():
            agent.current_dialogue = str(think_aloud)
            agent.dialogue_type = "thought"
            self.event_queue.push(
                "dialogue",
                f"{agent.name} thinks: {think_aloud}",
                "info",
                [agent.id],
                tick,
                agent.position,
            )
        else:
            agent.current_dialogue = None
            agent.dialogue_type = None

        self.builder.mark_agent_dirty(agent.id)

    def _update_relationship(
        self, agent_a: Agent, agent_b: Agent, tick: int, score_delta: float = 0.1
    ) -> None:
        """Update relationship data for two interacting agents."""
        if agent_b.id not in agent_a.relationships:
            agent_a.relationships[agent_b.id] = RelationshipData()
        if agent_a.id not in agent_b.relationships:
            agent_b.relationships[agent_a.id] = RelationshipData()

        agent_a.relationships[agent_b.id].interaction_count += 1
        agent_a.relationships[agent_b.id].last_interaction_tick = tick
        agent_a.relationships[agent_b.id].score = max(
            -1.0, min(1.0, agent_a.relationships[agent_b.id].score + score_delta)
        )

        agent_b.relationships[agent_a.id].interaction_count += 1
        agent_b.relationships[agent_a.id].last_interaction_tick = tick
        agent_b.relationships[agent_a.id].score = max(
            -1.0, min(1.0, agent_b.relationships[agent_a.id].score + score_delta)
        )

    async def _evaluate_trade_proposal(self, agent: Agent, proposal: dict) -> bool:
        """Evaluate a trade proposal via LLM. Returns True for accept, False for reject."""
        # Build a trade-specific prompt
        prompt = (
            f"Trade proposal from {proposal.get('from')}: "
            f"they offer {proposal.get('offer', {})} and request {proposal.get('request', {})}. "
            f"Your current inventory: {agent.inventory}. "
            f"Reply with ONLY a JSON object: {{'decision': 'accept' or 'reject'}}"
        )
        try:
            future = self.llm.call_async(agent.id, prompt)
            result = await asyncio.wait_for(future, timeout=0.5)
            if result.get("success") and result.get("data"):
                decision = result.get("data", {}).get("decision", "reject")
                return decision == "accept"
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass
        # Fallback: deterministic evaluation based on resource availability
        request = proposal.get("request", {})
        return all(agent.inventory.get(res, 0) >= qty for res, qty in request.items())

    async def _process_trade_proposals(self, tick: int) -> None:
        """Process pending trade proposals in agents' conversation queues."""
        proposals: list[tuple[Agent, dict]] = []
        for agent in self.agents:
            for msg in list(agent.conversation_queue):
                if msg.content.get("type") != "trade_proposal":
                    continue
                # Skip proposals created in the current tick — let the target see them first
                if msg.tick >= tick:
                    continue
                # Remove the proposal from queue so it's processed once
                agent.conversation_queue.remove(msg)
                proposals.append((agent, msg.content))

        async def _process_one(agent: Agent, proposal: dict) -> None:
            proposer_id = proposal.get("from")
            offer = proposal.get("offer", {})
            request = proposal.get("request", {})
            proposer = next((a for a in self.agents if a.id == proposer_id), None)
            if not proposer:
                return

            accepted = await self._evaluate_trade_proposal(agent, proposal)

            if accepted:
                # Verify both still have resources (race condition check)
                proposer_has = all(proposer.inventory.get(res, 0) >= qty for res, qty in offer.items())
                target_has = all(agent.inventory.get(res, 0) >= qty for res, qty in request.items())
                if proposer_has and target_has:
                    # Atomic swap
                    for res, qty in offer.items():
                        proposer.inventory[res] = proposer.inventory.get(res, 0) - qty
                        agent.inventory[res] = agent.inventory.get(res, 0) + qty
                    for res, qty in request.items():
                        agent.inventory[res] = agent.inventory.get(res, 0) - qty
                        proposer.inventory[res] = proposer.inventory.get(res, 0) + qty
                    self._update_relationship(proposer, agent, tick, score_delta=0.2)
                    self.event_queue.push(
                        "trade",
                        f"{proposer.name} traded {offer} for {request} with {agent.name}",
                        "info",
                        [proposer.id, agent.id],
                        tick,
                    )
                    return

            # Rejected or insufficient resources
            self.event_queue.push(
                "trade",
                f"{agent.name} rejected trade from {proposer.name}: insufficient resources",
                "info",
                [proposer.id, agent.id],
                tick,
            )

        if proposals:
            await asyncio.gather(*[_process_one(agent, proposal) for agent, proposal in proposals])

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

            # Age
            agent.age += 1

            # Clamp to [0, 100]
            agent.hunger = max(0.0, min(100.0, agent.hunger))
            agent.thirst = max(0.0, min(100.0, agent.thirst))
            agent.health = max(0.0, min(100.0, agent.health))
            agent.energy = max(0.0, min(100.0, agent.energy))

            # Relationship decay
            for other_id, rel in list(agent.relationships.items()):
                if tick - rel.last_interaction_tick > DECAY_INTERVAL:
                    rel.interaction_count = max(0, rel.interaction_count - 1)
                    rel.score = max(-1.0, min(1.0, rel.score - 0.01))
                    rel.last_interaction_tick = tick

            # Child maturity
            if agent.is_child and agent.age >= agent.maturity_age:
                agent.is_child = False
                agent.parent_id = None
                self.event_queue.push(
                    "maturity",
                    f"{agent.name} has reached maturity",
                    "info",
                    [agent.id],
                    tick,
                )

            if agent.health <= 0:
                if getattr(agent, '_combat_attacker_id', None):
                    cause = "violence"
                else:
                    cause = "thirst" if agent.thirst >= 100 else "starvation"
                dead_agents.append((agent, cause))
                continue

            # Death by old age
            if agent.age >= agent.max_age:
                dead_agents.append((agent, "old_age"))
                continue

            # Update tracked health for interruption detection
            self._agent_health[agent.id] = agent.health

        for agent, cause in dead_agents:
            self.colony_stats_collector.record_death()
            # F4: transfer inventory to faction
            self.faction_manager.transfer_inventory_on_death(agent)

            # F3: orphan adoption
            for child in list(self.agents):
                if child.is_child and child.parent_id == agent.id:
                    # Find nearest adult
                    nearest = None
                    nearest_dist = float("inf")
                    for other in self.agents:
                        if other.id == agent.id or other.id == child.id:
                            continue
                        if other.is_child:
                            continue
                        dist = math.hypot(
                            other.position[0] - child.position[0],
                            other.position[1] - child.position[1],
                        )
                        if dist < nearest_dist and dist <= INTERACTION_RADIUS:
                            nearest = other
                            nearest_dist = dist
                    if nearest:
                        child.parent_id = nearest.id
                        self.event_queue.push(
                            "adoption",
                            f"{nearest.name} adopted {child.name} after {agent.name} died",
                            "info",
                            [nearest.id, child.id],
                            tick,
                        )
                    else:
                        # No adopter — accelerate decay
                        child.health -= 2.0

            if cause == "violence":
                attacker_id = getattr(agent, '_combat_attacker_id', None)
                # Update relationships
                if attacker_id:
                    attacker = next((a for a in self.agents if a.id == attacker_id), None)
                    if attacker:
                        self._update_relationship(attacker, agent, tick, score_delta=-0.5)
                # Clear guarding and equipment flags
                agent.is_guarding = False
                agent.equipment = {"weapon": "fist", "armor": "none", "tool": "none"}
                # Emit combat_death event
                self.event_queue.push(
                    "combat_death",
                    f"{agent.name} was killed",
                    "critical",
                    [agent.id],
                    tick,
                    metadata={"cause": "violence", "attacker_id": attacker_id, "target_id": agent.id},
                )
            else:
                death_event = create_death_event(agent, tick, cause=cause)
                self.event_queue.push(
                    death_event.type,
                    death_event.description,
                    death_event.severity,
                    death_event.agent_ids,
                    tick,
                    metadata=death_event.metadata,
                )
            self.agents.remove(agent)
            if agent.id in self.fsms:
                del self.fsms[agent.id]
            self._agent_health.pop(agent.id, None)
            self.builder.mark_agent_removed(agent.id)
            logger.warning(f"{agent.name} died at tick {tick}")

    # ------------------------------------------------------------------
    # FSM runner
    # ------------------------------------------------------------------

    def _run_agent_fsm(self, agent: Agent, tick: int) -> None:
        """Execute one tick of the agent's FSM."""
        fsm = self.fsms[agent.id]

        # Combat interruption: if health dropped, force re-evaluation
        prev_health = self._agent_health.get(agent.id, agent.health)
        if agent.health < prev_health:
            if fsm.current_state == "executing":
                fsm.transition_to("evaluate")
            agent.is_guarding = False

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

    def _find_reproduction_partner(self, agent: Agent) -> Optional[Agent]:
        """Find a compatible reproduction partner nearby (gated by interactions)."""
        if agent.is_child:
            return None
        for other in self.agents:
            if other.id == agent.id:
                continue
            if other.is_child:
                continue
            if other.sex == agent.sex:
                continue
            if other.energy <= 20 or other.hunger >= 80 or other.thirst >= 80:
                continue
            if getattr(other, '_is_reproducing', False):
                continue
            if getattr(other, 'age', 0) < 100:  # too young
                continue
            # F8: require interaction threshold
            rel = agent.relationships.get(other.id)
            if not rel or rel.interaction_count < INTERACTION_THRESHOLD:
                continue
            dist = math.hypot(
                agent.position[0] - other.position[0],
                agent.position[1] - other.position[1],
            )
            if dist <= INTERACTION_RADIUS * 2:  # wider range
                return other
        return None

    def _create_offspring(self, parent1: Agent, parent2: Agent, tick: int) -> Agent:
        """Create a new Agent as offspring of two parents."""
        import random

        # Spawn adjacent to parent1 (search radius 2)
        child_pos = (parent1.position[0], parent1.position[1])
        for radius in range(1, 3):
            found = False
            for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)]:
                if radius == 1 and (dx, dy) == (0, 0):
                    continue
                nx, ny = int(parent1.position[0]) + dx * radius, int(parent1.position[1]) + dy * radius
                if (
                    0 <= nx < self.world.width
                    and 0 <= ny < self.world.height
                    and not self._is_tile_occupied(nx, ny)
                ):
                    child_pos = (float(nx), float(ny))
                    found = True
                    break
            if found:
                break

        def inherit(a1_val, a2_val):
            return max(0, min(100, (a1_val + a2_val) // 2 + random.randint(-10, 10)))

        # F3: derive stats from parent with ±15 random offset
        def inherit_with_offset(parent_val):
            return max(0, min(100, parent_val + random.randint(-15, 15)))

        child = Agent(
            id=f"agent_{uuid.uuid4().hex[:6]}",
            name=self._generate_agent_name(),
            position=child_pos,
            role=random.choice([parent1.role, parent2.role]),
            strength=inherit(parent1.strength, parent2.strength),
            intelligence=inherit(parent1.intelligence, parent2.intelligence),
            sociability=inherit(parent1.sociability, parent2.sociability),
            speed=inherit(parent1.speed, parent2.speed),
            sex=random.choice(["male", "female"]),
            age=0,
            max_age=random.randint(2000, 5000),
            is_child=True,
            parent_id=parent1.id,
            maturity_age=random.randint(300, 700),
        )
        return child

    def _generate_agent_name(self) -> str:
        """Generate a random agent name."""
        import random
        names = ["Rax", "Nyx", "Vex", "Lux", "Tix", "Bix", "Zan", "Riv", "Fen", "Gor",
                 "Lia", "Nia", "Tia", "Mya", "Rya", "Ena", "Ula", "Ora", "Ada", "Iva"]
        return random.choice(names)

    def _try_role_action(
        self,
        agent: Agent,
        fsm: FSM,
        action_name: str,
        food_nearby: list,
        water_nearby: list,
    ) -> bool:
        """Attempt to execute a role-priority action if conditions are met.

        Returns *True* if the action was triggered.
        """
        if action_name == "eat":
            if agent.hunger > CRITICAL_HUNGER and agent.inventory.get("berries", 0) > 0:
                agent.current_action = "eat"
                agent.current_action_emoji = "🍎"
                agent.action_duration = 3
                agent.action_progress = 0.0
                fsm.transition_to("executing")
                return True
        elif action_name == "drink":
            if agent.thirst > CRITICAL_THIRST:
                for r in water_nearby:
                    if abs(r[0] - agent.position[0]) <= 1 and abs(r[1] - agent.position[1]) <= 1:
                        agent.current_action = "drink"
                        agent.current_action_emoji = "💧"
                        agent.action_duration = 3
                        agent.action_progress = 0.0
                        fsm.transition_to("executing")
                        return True
        elif action_name == "gather":
            if agent.hunger > CRITICAL_HUNGER:
                for r in food_nearby:
                    if abs(r[0] - agent.position[0]) <= 1 and abs(r[1] - agent.position[1]) <= 1:
                        agent.current_action = "gather"
                        agent.current_action_emoji = "🫐"
                        agent.action_duration = 3
                        agent.action_progress = 0.0
                        fsm.transition_to("executing")
                        return True
        elif action_name == "rest":
            if agent.energy < 30:
                agent.current_action = "rest"
                agent.current_action_emoji = "💤"
                agent.action_duration = get_action_duration(ActionType.REST, agent)
                agent.action_progress = 0.0
                fsm.transition_to("executing")
                return True
        elif action_name == "explore":
            for y in range(self.world.height):
                for x in range(self.world.width):
                    if (x, y) not in agent.explored_tiles:
                        agent.current_action = "explore"
                        agent.current_action_emoji = "🧭"
                        agent.action_duration = get_action_duration(ActionType.EXPLORE, agent)
                        agent.action_progress = 0.0
                        fsm.transition_to("executing")
                        return True
        elif action_name == "mine":
            cx, cy = int(agent.position[0]), int(agent.position[1])
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < self.world.width and 0 <= ny < self.world.height:
                        tile = self.world.get_tile(nx, ny)
                        if tile.resource_type in ("stone", "iron_ore") and tile.amount > 0:
                            agent.current_action = "mine"
                            agent.current_action_emoji = "⛏️"
                            agent.action_duration = get_action_duration(ActionType.MINE, agent)
                            agent.action_progress = 0.0
                            fsm.transition_to("executing")
                            return True
        elif action_name == "attack":
            for other in self.agents:
                if other.id != agent.id:
                    dist = math.hypot(
                        agent.position[0] - other.position[0],
                        agent.position[1] - other.position[1],
                    )
                    if dist <= 5:
                        agent.current_action = "attack"
                        agent.current_action_emoji = "⚔️"
                        agent.action_duration = 3
                        agent.action_progress = 0.0
                        fsm.transition_to("executing")
                        return True
        elif action_name == "build":
            cx, cy = int(agent.position[0]), int(agent.position[1])
            from app.simulation.structures import STRUCTURE_COSTS
            for structure_type, costs in STRUCTURE_COSTS.items():
                if all(agent.inventory.get(res, 0) >= qty for res, qty in costs.items()):
                    tile = self.world.get_tile(cx, cy)
                    if tile.resource_type is None and not tile.blocked and self.world.structures.get_structure_at((cx, cy)) is None:
                        agent.current_action = "build"
                        agent.current_action_emoji = "🔧"
                        agent.action_duration = get_action_duration(ActionType.BUILD, agent)
                        agent.action_progress = 0.0
                        fsm.transition_to("executing")
                        return True
            return False
        return False

    def _run_survival_chain(
        self,
        agent: Agent,
        fsm: FSM,
        tick: int,
        food_nearby: list,
        water_nearby: list,
    ) -> None:
        """Original hardcoded survival evaluation (items 1‑7)."""
        # ── 1. Eat from inventory if hungry ──
        if agent.hunger > CRITICAL_HUNGER and agent.inventory.get("berries", 0) > 0:
            agent.current_action = "eat"
            agent.current_action_emoji = "🍎"
            agent.action_duration = 3
            agent.action_progress = 0.0
            fsm.transition_to("executing")
            return

        # ── 2. Drink if thirsty and at water ──
        if agent.thirst > CRITICAL_THIRST:
            for r in water_nearby:
                if abs(r[0] - agent.position[0]) <= 1 and abs(r[1] - agent.position[1]) <= 1:
                    agent.current_action = "drink"
                    agent.current_action_emoji = "💧"
                    agent.action_duration = 3
                    agent.action_progress = 0.0
                    fsm.transition_to("executing")
                    return

        # ── 3. Gather food if hungry and at food source ──
        if agent.hunger > CRITICAL_HUNGER:
            for r in food_nearby:
                if abs(r[0] - agent.position[0]) <= 1 and abs(r[1] - agent.position[1]) <= 1:
                    agent.current_action = "gather"
                    agent.current_action_emoji = "🫐"
                    agent.action_duration = 3
                    agent.action_progress = 0.0
                    fsm.transition_to("executing")
                    return

        # ── 4. Rest if energy is low ──
        if agent.energy < 30:
            agent.current_action = "rest"
            agent.current_action_emoji = "💤"
            agent.action_duration = get_action_duration(ActionType.REST, agent)
            agent.action_progress = 0.0
            fsm.transition_to("executing")
            return

        # ── 5. Move toward food/water if critical ──
        if agent.hunger > CRITICAL_HUNGER or agent.thirst > CRITICAL_THIRST:
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

        # ── 6. Reproduce (lax thresholds — civilization first!) ──
        if len(self.agents) >= MAX_POPULATION:
            pass  # fall through to LLM trigger
        elif (agent.energy > 30 and agent.hunger < 70 and agent.thirst < 70):
            last_repro = getattr(agent, '_last_reproduction_tick', -999)
            if tick - last_repro < REPRODUCTION_COOLDOWN:
                pass  # fall through to LLM trigger
            else:
                partner = self._find_reproduction_partner(agent)
                if partner:
                    agent._is_reproducing = True
                    partner._is_reproducing = True
                    agent.current_action = "reproduce"
                    agent.current_action_emoji = "❤️"
                    agent.action_duration = get_action_duration(ActionType.REPRODUCE, agent)
                    agent.action_progress = 0.0
                    partner.current_action = "reproduce"
                    partner.current_action_emoji = "❤️"
                    partner.action_duration = get_action_duration(ActionType.REPRODUCE, partner)
                    partner.action_progress = 0.0
                    agent._reproduce_partner_id = partner.id
                    partner._reproduce_partner_id = agent.id
                    fsm.transition_to("executing")
                    fsm_partner = self.fsms[partner.id]
                    if fsm_partner.current_state == "idle":
                        fsm_partner.transition_to("evaluate")
                    if fsm_partner.current_state != "executing":
                        fsm_partner.transition_to("executing")
                    return

        # Needs met → try LLM for higher-level planning
        if not agent.active_plan and not agent.llm_call_pending:
            fsm.transition_to("llm_trigger")
        elif agent.active_plan:
            # Continue with existing plan — skip steps disallowed by role
            while agent.plan_step_index < len(agent.active_plan["steps"]):
                step = agent.active_plan["steps"][agent.plan_step_index]
                action_type = ActionType(step["action"])
                if roles_module.role_allows_action(agent.role, action_type):
                    break
                agent.plan_step_index += 1
            else:
                # All remaining steps disallowed — clear plan and idle
                agent.active_plan = None
                agent.plan_step_index = 0
                agent.current_action = "idle"
                agent.current_action_emoji = "💤"
                fsm.transition_to("idle")
                return

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

    def _fsm_evaluate(self, agent: Agent, fsm: FSM, tick: int) -> None:
        """Check needs and decide next state.

        New flow:
        0. Feed child if caregiver and child is critical
        1. Check role priorities (highest score first)
        2. Fallback to hardcoded survival chain
        3. LLM for higher-level planning
        """
        nearby = self.world.get_nearby_resources(agent.position, radius=8)
        food_nearby = [r for r in nearby if r[2] in ("berries", "tree")]
        water_nearby = [r for r in nearby if r[2] == "water"]

        # ── 0. Feed child if caregiver and child is critical ──
        if not agent.is_child and agent.inventory.get("berries", 0) > 0:
            for child in self.agents:
                if child.is_child and child.parent_id == agent.id:
                    dist = math.hypot(
                        agent.position[0] - child.position[0],
                        agent.position[1] - child.position[1],
                    )
                    if dist <= INTERACTION_RADIUS:
                        if child.hunger > 70:
                            agent.current_action = "feed_child"
                            agent.current_action_emoji = "🍼"
                            agent.action_duration = get_action_duration(ActionType.FEED_CHILD, agent)
                            agent.action_progress = 0.0
                            agent.active_plan = {
                                "steps": [{"action": "feed_child", "target": None, "child_id": child.id}]
                            }
                            agent.plan_step_index = 0
                            fsm.transition_to("executing")
                            return
                        elif child.thirst > 70:
                            nearby = self.world.get_nearby_resources(agent.position, radius=8)
                            water_nearby = [r for r in nearby if r[2] == "water"]
                            if water_nearby:
                                target = (water_nearby[0][0], water_nearby[0][1])
                                agent.current_action = "seeking water"
                                agent.current_action_emoji = "🍼"
                                agent.target_position = (float(target[0]), float(target[1]))
                                agent.move_path = self.world.find_path(
                                    (int(agent.position[0]), int(agent.position[1])), target
                                )
                                agent.move_progress = 0.0
                                fsm.transition_to("moving")
                                return
                    else:
                        target = (int(child.position[0]), int(child.position[1]))
                        agent.current_action = "seeking child"
                        agent.current_action_emoji = "🍼"
                        agent.target_position = (float(target[0]), float(target[1]))
                        agent.move_path = self.world.find_path(
                            (int(agent.position[0]), int(agent.position[1])), target
                        )
                        agent.move_progress = 0.0
                        fsm.transition_to("moving")
                        return

        # ── 1. Role priorities ──
        role_config = roles_module.get_role_config(agent.role)
        priorities = sorted(role_config.get("priorities", []), key=lambda x: x[1], reverse=True)
        for action_name, _score in priorities:
            if self._try_role_action(agent, fsm, action_name, food_nearby, water_nearby):
                return

        # ── 2. Hardcoded survival chain ──
        self._run_survival_chain(agent, fsm, tick, food_nearby, water_nearby)

    def _is_tile_occupied(self, x: int, y: int, exclude_id: str | None = None) -> bool:
        """Check if a tile is occupied by another agent."""
        for other in self.agents:
            if exclude_id and other.id == exclude_id:
                continue
            ox, oy = int(other.position[0]), int(other.position[1])
            if ox == x and oy == y:
                return True
        return False

    def _fsm_moving(self, agent: Agent, fsm: FSM, tick: int) -> None:
        """Advance along path toward target with collision avoidance."""
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

        # ── Collision avoidance ──
        next_pos = agent.move_path[0]
        nx, ny = next_pos

        if self._is_tile_occupied(nx, ny, agent.id):
            # Tile occupied — try to nudge to a nearby free tile
            moved = False
            for dx, dy in [(1,0), (-1,0), (0,1), (0,-1), (1,1), (-1,1), (1,-1), (-1,-1)]:
                adj_x, adj_y = nx + dx, ny + dy
                if (self.world.is_passable(adj_x, adj_y) and 
                    not self._is_tile_occupied(adj_x, adj_y, agent.id)):
                    agent.position = (float(adj_x), float(adj_y))
                    self.builder.mark_agent_dirty(agent.id)
                    moved = True
                    break
            if not moved:
                # Can't move anywhere — wait a tick
                self.builder.mark_agent_dirty(agent.id)
                return  # stay in moving, try again next tick
            # Nudged to adjacent tile; don't consume the path step yet
        else:
            # Tile is free — advance normally
            agent.move_path.pop(0)
            agent.position = (float(nx), float(ny))
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
                # For trade/feed_child, pass the plan step so extra params are available
                step = None
                if agent.active_plan and action_type in (ActionType.TRADE, ActionType.FEED_CHILD):
                    step = agent.active_plan["steps"][agent.plan_step_index]
                if action_type in (ActionType.FEED_CHILD, ActionType.ATTACK):
                    result = handler(agent, self.world, target, step, self.agents)
                else:
                    result = handler(agent, self.world, target, step)
                agent.last_action_result = result

                # Mark new structures as dirty for snapshot delta
                if action_type == ActionType.BUILD and result.success:
                    structure_id = result.state_changes.get("structure_id")
                    if structure_id:
                        self.builder.mark_structure_dirty(structure_id)

                # F5: enqueue trade proposal in target's conversation queue
                if action_type == ActionType.TRADE and result.success and step:
                    target_id = step.get("target")
                    target_agent = next((a for a in self.agents if a.id == target_id), None)
                    if target_agent:
                        from app.simulation.conversation import Message
                        target_agent.conversation_queue.append(
                            Message(
                                sender_id=agent.id,
                                content={
                                    "type": "trade_proposal",
                                    "from": agent.id,
                                    "offer": step.get("offer", {}),
                                    "request": step.get("request", {}),
                                },
                                tick=tick,
                            )
                        )

                if result.interrupted or not result.success:
                    fsm.transition_to("evaluate")
                    return

            # Handle special actions (not in registry)
            if action_type == ActionType.REPRODUCE:
                partner_id = getattr(agent, '_reproduce_partner_id', None)
                partner = next((a for a in self.agents if a.id == partner_id), None)
                if partner:
                    child = self._create_offspring(agent, partner, tick)
                    self.add_agent(child)
                    from app.simulation.event_queue import create_birth_event
                    birth_ev = create_birth_event(child, agent, partner, tick)
                    self.event_queue.push(
                        birth_ev.type, birth_ev.description, birth_ev.severity,
                        birth_ev.agent_ids, tick, birth_ev.position, birth_ev.metadata,
                    )
                # Clean up
                for a in [agent, partner]:
                    if a:
                        a._is_reproducing = False
                        a._reproduce_partner_id = None
                        a._last_reproduction_tick = tick

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

        # Update tracked health after potential combat resolution
        self._agent_health[agent.id] = agent.health

    def _fsm_llm_trigger(self, agent: Agent, fsm: FSM, tick: int) -> None:
        """Queue an async LLM call."""
        if agent.llm_call_pending:
            fsm.transition_to("llm_waiting")
            return

        # Cooldown: don't retry LLM more than once every 30 ticks after a failed attempt
        last = getattr(agent, '_last_llm_tick', -999)
        if last > 0 and tick - last < 30:
            agent.last_thought = "(waiting before retrying)"
            fsm.transition_to("llm_waiting")
            return

        prompt = self.llm.build_prompt(agent, self.world)
        # F1: consume last_action_result after prompt build to prevent stale accumulation
        agent.last_action_result = None
        agent.llm_future = self.llm.call_async(agent.id, prompt)
        agent.llm_call_pending = True
        agent._last_llm_tick = tick
        agent.last_thought = "Thinking about what to do next..."
        self.builder.mark_agent_dirty(agent.id)
        fsm.transition_to("llm_waiting")

    def _fsm_llm_waiting(self, agent: Agent, fsm: FSM, tick: int) -> None:
        """Wait for LLM response while acting on instinct."""
        # If no future is set (cooldown or first trigger misfire), go back to evaluate
        if not agent.llm_future:
            # F1: discard stale last_action_result on fallback
            agent.last_action_result = None
            fsm.transition_to("evaluate")
            return

        if agent.llm_future.done():
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
                    self._process_say_to(agent, plan, tick)
                    logger.debug(
                        f"{agent.name} received new plan: "
                        f"{plan.get('intention', '')}"
                    )
                else:
                    err = result.get('error', 'unknown')
                    logger.warning(f"{agent.name} LLM call failed: [{err}]")
                    agent.last_thought = f"Plan failed: {err}"
            except Exception as e:
                logger.error(f"{agent.name} LLM future error: {e}")

            agent.llm_call_pending = False
            agent.llm_future = None
            self.builder.mark_agent_dirty(agent.id)
            fsm.transition_to("evaluate")
        else:
            # Still waiting — act on instinct
            agent.last_thought = "Waiting for guidance..."
            agent.current_action = "waiting"
            agent.current_action_emoji = "⏳"
            self.builder.mark_agent_dirty(agent.id)

            # Instinct: if hungry, eat from inventory first
            if agent.hunger > CRITICAL_HUNGER and agent.inventory.get("berries", 0) > 0:
                agent.current_action = "eat"
                agent.current_action_emoji = "🍎"
                agent.action_duration = 3
                agent.action_progress = 0.0
                fsm.transition_to("executing")
            # Rest if energy low
            elif agent.energy < 30:
                agent.current_action = "rest"
                agent.current_action_emoji = "💤"
                agent.action_duration = get_action_duration(ActionType.REST, agent)
                agent.action_progress = 0.0
                fsm.transition_to("executing")
            # Otherwise move toward nearest resource
            elif agent.hunger > CRITICAL_HUNGER or agent.thirst > CRITICAL_THIRST:
                nearby = self.world.get_nearby_resources(agent.position, radius=5)
                target = None
                for r in nearby:
                    if r[2] in ("berries", "water") and r[3] > 0:
                        target = (r[0], r[1])
                        break
                if target and not agent.move_path:
                    start = (int(agent.position[0]), int(agent.position[1]))
                    agent.move_path = self.world.find_path(start, target)
                    agent.target_position = (float(target[0]), float(target[1]))
                    agent.current_action = "seeking water" if agent.thirst > agent.hunger else "seeking food"
                    agent.current_action_emoji = "💧" if agent.thirst > agent.hunger else "🍎"
                    agent.move_progress = 0.0
                    fsm.transition_to("moving")

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
                self._process_say_to(agent, plan, tick)
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
