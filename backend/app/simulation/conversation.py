"""Conversation system: messages and encounter detection."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.simulation.agent import Agent
from app.simulation.event_queue import SimEvent


@dataclass
class Message:
    sender_id: str
    content: dict  # structured: {"type": "greeting"|"share_knowledge"|"trade_proposal"|...}
    tick: int


class ConversationManager:
    max_pairs_per_tick: int = 5
    max_queue_size: int = 50

    def __init__(self) -> None:
        self._pending_pairs: list[tuple[str, str]] = []

    def _enqueue_message(self, agent: Agent, message: Message) -> None:
        """Add message to agent's queue, respecting max size (FIFO discard)."""
        agent.conversation_queue.append(message)
        while len(agent.conversation_queue) > self.max_queue_size:
            agent.conversation_queue.pop(0)

    def detect_encounters(
        self, agents: list[Agent], radius: float, tick: int
    ) -> list[SimEvent]:
        """Find nearby agent pairs and enqueue greeting messages.

        Returns list of socialize SimEvents.
        """
        events: list[SimEvent] = []
        # First, add any deferred pairs from previous ticks
        pairs_to_process = list(self._pending_pairs)
        self._pending_pairs = []

        # Find new pairs
        new_pairs: list[tuple[str, str]] = []
        for i, a1 in enumerate(agents):
            for a2 in agents[i + 1 :]:
                dist = math.hypot(
                    a1.position[0] - a2.position[0],
                    a1.position[1] - a2.position[1],
                )
                if dist <= radius:
                    new_pairs.append((a1.id, a2.id))

        pairs_to_process.extend(new_pairs)

        # Process up to max_pairs_per_tick
        processed = 0
        for a1_id, a2_id in pairs_to_process:
            if processed >= self.max_pairs_per_tick:
                self._pending_pairs.append((a1_id, a2_id))
                continue
            a1 = next((a for a in agents if a.id == a1_id), None)
            a2 = next((a for a in agents if a.id == a2_id), None)
            if a1 and a2:
                self._enqueue_message(
                    a1,
                    Message(
                        sender_id=a2.id,
                        content={"type": "greeting", "agent_name": a2.name},
                        tick=tick,
                    ),
                )
                self._enqueue_message(
                    a2,
                    Message(
                        sender_id=a1.id,
                        content={"type": "greeting", "agent_name": a1.name},
                        tick=tick,
                    ),
                )

                # F2+F6: share knowledge if one knows something the other doesn't
                for sharer, receiver in [(a1, a2), (a2, a1)]:
                    for subtype, props in sharer.knowledge.items():
                        if subtype not in receiver.knowledge:
                            self._enqueue_message(
                                receiver,
                                Message(
                                    sender_id=sharer.id,
                                    content={
                                        "type": "share_knowledge",
                                        "subtype": subtype,
                                        "properties": dict(props),
                                    },
                                    tick=tick,
                                ),
                            )
                            # Knowledge is applied when receiver processes conversation_queue,
                            # not directly here.
                            events.append(
                                SimEvent(
                                    event_id=f"knowledge_shared_{tick}_{sharer.id}_{receiver.id}",
                                    type="knowledge_shared",
                                    severity="info",
                                    description=f"{sharer.name} shared knowledge about {subtype} with {receiver.name}",
                                    agent_ids=[sharer.id, receiver.id],
                                    tick=tick,
                                )
                            )
                            break  # share only one per encounter

                events.append(
                    SimEvent(
                        event_id=f"socialize_{tick}_{a1_id}_{a2_id}",
                        type="socialize",
                        severity="info",
                        description=f"{a1.name} and {a2.name} greeted each other",
                        agent_ids=[a1_id, a2_id],
                        tick=tick,
                        position=(
                            (a1.position[0] + a2.position[0]) / 2,
                            (a1.position[1] + a2.position[1]) / 2,
                        ),
                    )
                )
                processed += 1

        return events

    def process_next_pair(
        self, agent_a: Agent, agent_b: Agent, tick: int
    ) -> tuple[Message, Message] | None:
        """Process a single encounter pair (used for manual/testing)."""
        msg_a = Message(
            sender_id=agent_b.id,
            content={"type": "greeting", "agent_name": agent_b.name},
            tick=tick,
        )
        msg_b = Message(
            sender_id=agent_a.id,
            content={"type": "greeting", "agent_name": agent_a.name},
            tick=tick,
        )
        self._enqueue_message(agent_a, msg_a)
        self._enqueue_message(agent_b, msg_b)
        return (msg_a, msg_b)


__all__ = ["Message", "ConversationManager"]
