"""
Agent Conversation Coordinator
Manages multi-agent conversations with turn-taking, context passing, and real-time coordination
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List, Callable, Set, Tuple
from uuid import uuid4
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

from .conversation_types import (
    ConversationState, ConversationContext, AgentParticipant, ConversationTurn,
    ConversationSession, AgentRole, MessageRole, A2AMessage, MessagePart,
    AgentSwitchEvent, ConversationUpdateEvent,
    create_conversation_id, create_message_id, current_timestamp
)
from .a2a_streaming import A2AConversationStreamer, A2AStreamingClient
from ..a2a_client import A2ACardResolver
from .worker_manager import WorkerAgentManager

logger = logging.getLogger(__name__)
coordination_logger = logging.getLogger('agents.conversation_coordination')


@dataclass
class ConversationRule:
    """Rules for conversation management"""
    max_participants: int = 5
    max_turn_duration: int = 120  # seconds
    max_conversation_duration: int = 1800  # 30 minutes
    auto_escalation: bool = True
    require_consensus: bool = False
    allow_interruption: bool = True
    turn_timeout: int = 30  # seconds


@dataclass
class ConversationMetrics:
    """Conversation performance metrics"""
    total_turns: int = 0
    total_duration: float = 0.0
    average_turn_duration: float = 0.0
    agent_participation: Dict[str, int] = field(default_factory=dict)
    message_count: int = 0
    error_count: int = 0
    successful_delegations: int = 0


class TurnManager:
    """Manages turn-taking in multi-agent conversations"""

    def __init__(self, conversation_id: str, rules: ConversationRule):
        self.conversation_id = conversation_id
        self.rules = rules
        self.turn_queue: List[str] = []
        self.current_speaker: Optional[str] = None
        self.turn_start_time: Optional[datetime] = None
        self.turn_history: List[Tuple[str, datetime, Optional[datetime]]] = []
        self._turn_lock = asyncio.Lock()

    async def request_turn(self, agent_id: str, priority: int = 0) -> bool:
        """Request speaking turn for agent"""
        async with self._turn_lock:
            if agent_id not in self.turn_queue:
                if priority > 0:
                    # High priority - insert at beginning
                    self.turn_queue.insert(0, agent_id)
                else:
                    # Normal priority - add to end
                    self.turn_queue.append(agent_id)

                coordination_logger.info(
                    f"Turn requested: {agent_id} (priority: {priority}) in conversation {self.conversation_id}"
                )
                return True
            return False

    async def grant_turn(self) -> Optional[str]:
        """Grant turn to next agent in queue"""
        async with self._turn_lock:
            if self.turn_queue:
                next_speaker = self.turn_queue.pop(0)

                # Complete previous turn
                if self.current_speaker and self.turn_start_time:
                    turn_end = datetime.now()
                    duration = (turn_end - self.turn_start_time).total_seconds()

                    # Update turn history
                    for i, (agent, start, end) in enumerate(self.turn_history):
                        if agent == self.current_speaker and end is None:
                            self.turn_history[i] = (agent, start, turn_end)
                            break

                # Start new turn
                self.current_speaker = next_speaker
                self.turn_start_time = datetime.now()
                self.turn_history.append((next_speaker, self.turn_start_time, None))

                coordination_logger.info(
                    f"Turn granted to: {next_speaker} in conversation {self.conversation_id}"
                )
                return next_speaker
            return None

    async def release_turn(self, agent_id: str) -> bool:
        """Release current turn"""
        async with self._turn_lock:
            if self.current_speaker == agent_id:
                turn_end = datetime.now()

                # Update turn history
                for i, (agent, start, end) in enumerate(self.turn_history):
                    if agent == agent_id and end is None:
                        self.turn_history[i] = (agent, start, turn_end)
                        break

                self.current_speaker = None
                self.turn_start_time = None

                coordination_logger.info(
                    f"Turn released by: {agent_id} in conversation {self.conversation_id}"
                )
                return True
            return False

    def get_turn_statistics(self) -> Dict[str, Any]:
        """Get turn statistics"""
        total_turns = len([h for h in self.turn_history if h[2] is not None])
        agent_turns = defaultdict(int)
        total_duration = 0.0

        for agent, start, end in self.turn_history:
            if end:
                duration = (end - start).total_seconds()
                agent_turns[agent] += 1
                total_duration += duration

        return {
            "totalTurns": total_turns,
            "totalDuration": total_duration,
            "averageTurnDuration": total_duration / total_turns if total_turns > 0 else 0,
            "agentTurns": dict(agent_turns),
            "currentSpeaker": self.current_speaker,
            "queueLength": len(self.turn_queue)
        }


class ConversationCoordinator:
    """
    Main coordinator for multi-agent conversations
    Handles participant management, turn-taking, and real-time coordination
    """

    def __init__(self):
        self.active_conversations: Dict[str, ConversationSession] = {}
        self.turn_managers: Dict[str, TurnManager] = {}
        self.conversation_rules: Dict[str, ConversationRule] = {}
        self.metrics: Dict[str, ConversationMetrics] = {}
        self.worker_manager = WorkerAgentManager()
        self.streamer = A2AConversationStreamer()
        self._coordination_lock = asyncio.Lock()

    async def create_conversation(
        self,
        topic: str,
        initiator_id: str,
        participant_agent_slugs: List[str],
        rules: Optional[ConversationRule] = None,
        context_id: str = None,
        session_id: str = None
    ) -> ConversationSession:
        """Create new multi-agent conversation"""
        conversation_id = create_conversation_id()
        rules = rules or ConversationRule()

        coordination_logger.info(
            f"Creating conversation {conversation_id}: topic='{topic}', "
            f"initiator={initiator_id}, participants={participant_agent_slugs}"
        )

        # Validate participants
        validated_participants = await self._validate_participants(participant_agent_slugs)
        if not validated_participants:
            raise ValueError("No valid participants found")

        # Create conversation context
        context = ConversationContext(
            conversationId=conversation_id,
            contextId=context_id or f"ctx_{conversation_id}",
            sessionId=session_id or f"session_{uuid4().hex[:12]}",
            initiatedBy=initiator_id,
            topic=topic,
            state=ConversationState.INITIATED.value,
            participants=validated_participants,
            currentSpeaker=None,
            turnHistory=[],
            createdAt=current_timestamp(),
            updatedAt=current_timestamp(),
            metadata={
                "rules": rules.__dict__,
                "createdBy": "ConversationCoordinator"
            }
        )

        # Create conversation session
        session = ConversationSession(
            context=context,
            turns=[]
        )

        # Initialize management components
        async with self._coordination_lock:
            self.active_conversations[conversation_id] = session
            self.turn_managers[conversation_id] = TurnManager(conversation_id, rules)
            self.conversation_rules[conversation_id] = rules
            self.metrics[conversation_id] = ConversationMetrics()

        coordination_logger.info(f"Conversation {conversation_id} created successfully")
        return session

    async def _validate_participants(self, agent_slugs: List[str]) -> List[AgentParticipant]:
        """Validate and create participant objects"""
        participants = []

        for slug in agent_slugs:
            try:
                # Get agent info from worker manager
                worker = await self.worker_manager.get_worker(slug)
                if worker:
                    participant = AgentParticipant(
                        agentId=f"agent_{slug}_{uuid4().hex[:8]}",
                        agentSlug=slug,
                        agentName=worker.agent_name,
                        role=AgentRole.PARTICIPANT.value,
                        capabilities=worker.capabilities,
                        status="online",
                        joinedAt=current_timestamp()
                    )
                    participants.append(participant)
                    coordination_logger.info(f"Validated participant: {slug} ({worker.agent_name})")
                else:
                    coordination_logger.warning(f"Could not validate agent: {slug}")
            except Exception as e:
                coordination_logger.error(f"Error validating agent {slug}: {e}")

        return participants

    async def start_conversation(
        self,
        conversation_id: str,
        initial_message: str,
        websocket_callback: Optional[Callable] = None
    ) -> bool:
        """Start conversation with initial message"""
        if conversation_id not in self.active_conversations:
            coordination_logger.error(f"Conversation {conversation_id} not found")
            return False

        session = self.active_conversations[conversation_id]
        session.context["state"] = ConversationState.ACTIVE.value
        session.context["updatedAt"] = current_timestamp()

        coordination_logger.info(f"Starting conversation {conversation_id} with message: {initial_message[:100]}...")

        try:
            # Create initial message
            initial_msg = A2AMessage(
                messageId=create_message_id(),
                role=MessageRole.USER.value,
                parts=[MessagePart(
                    kind="text",
                    text=initial_message,
                    file=None,
                    mimeType=None,
                    data=None
                )],
                contextId=session.context["contextId"],
                timestamp=current_timestamp(),
                agentId=session.context["initiatedBy"],
                metadata={"conversationId": conversation_id}
            )

            # Send conversation start event
            if websocket_callback:
                await websocket_callback({
                    "type": "conversation_started",
                    "conversationId": conversation_id,
                    "context": session.context,
                    "initialMessage": initial_msg
                })

            # Determine first speaker (coordinator logic)
            first_speaker = await self._select_first_speaker(conversation_id, initial_message)
            if first_speaker:
                # Request and grant turn to first speaker
                turn_manager = self.turn_managers[conversation_id]
                await turn_manager.request_turn(first_speaker["agentId"], priority=1)
                granted_agent = await turn_manager.grant_turn()

                if granted_agent:
                    session.context["currentSpeaker"] = granted_agent

                    # Start conversation with selected agent
                    await self._process_agent_turn(
                        conversation_id=conversation_id,
                        agent_participant=first_speaker,
                        message=initial_message,
                        websocket_callback=websocket_callback
                    )

                    return True

            coordination_logger.error(f"Could not start conversation {conversation_id} - no valid first speaker")
            return False

        except Exception as e:
            coordination_logger.error(f"Error starting conversation {conversation_id}: {e}")
            session.context["state"] = ConversationState.FAILED.value
            return False

    async def _select_first_speaker(self, conversation_id: str, initial_message: str) -> Optional[AgentParticipant]:
        """Select first speaker based on message content and agent capabilities"""
        session = self.active_conversations[conversation_id]
        participants = session.context["participants"]

        if not participants:
            return None

        # For now, use simple selection logic (can be enhanced with LLM)
        # Priority: specialist agents first, then general agents
        specialist_agents = [p for p in participants if "specialist" in p["agentSlug"]]
        general_agents = [p for p in participants if "general" in p["agentSlug"] or "test" in p["agentSlug"]]

        # Select based on message content
        if "flight" in initial_message.lower() or "항공" in initial_message.lower():
            flight_agents = [p for p in specialist_agents if "flight" in p["agentSlug"]]
            if flight_agents:
                return flight_agents[0]

        # Default to first specialist or general agent
        if specialist_agents:
            return specialist_agents[0]
        elif general_agents:
            return general_agents[0]
        else:
            return participants[0]

    async def _process_agent_turn(
        self,
        conversation_id: str,
        agent_participant: AgentParticipant,
        message: str,
        websocket_callback: Optional[Callable] = None
    ):
        """Process agent's turn in conversation"""
        session = self.active_conversations[conversation_id]
        agent_slug = agent_participant["agentSlug"]

        coordination_logger.info(f"Processing turn for {agent_slug} in conversation {conversation_id}")

        try:
            # Create turn record
            turn = ConversationTurn(
                turnId=f"turn_{uuid4().hex[:12]}",
                conversationId=conversation_id,
                agentId=agent_participant["agentId"],
                agentSlug=agent_slug,
                message=A2AMessage(
                    messageId=create_message_id(),
                    role=MessageRole.USER.value,
                    parts=[MessagePart(kind="text", text=message, file=None, mimeType=None, data=None)],
                    contextId=session.context["contextId"],
                    timestamp=current_timestamp(),
                    agentId=agent_participant["agentId"],
                    metadata={}
                ),
                startedAt=datetime.now()
            )

            session.turns.append(turn)
            session.currentTurn = turn

            # Get worker agent and process message
            worker = await self.worker_manager.get_worker(agent_slug)
            if worker:
                # Send turn start event
                if websocket_callback:
                    await websocket_callback({
                        "type": "agent_turn_started",
                        "conversationId": conversation_id,
                        "agent": agent_participant,
                        "turn": turn.to_dict()
                    })

                # Process message with worker agent
                response = await worker.process_request(
                    user_input=message,
                    context_id=session.context["contextId"],
                    session_id=session.context["sessionId"],
                    user_name="conversation_coordinator"
                )

                # Complete turn
                turn.completedAt = datetime.now()
                turn.duration = (turn.completedAt - turn.startedAt).total_seconds()

                # Send response event
                if websocket_callback:
                    await websocket_callback({
                        "type": "agent_turn_completed",
                        "conversationId": conversation_id,
                        "agent": agent_participant,
                        "response": response,
                        "turn": turn.to_dict()
                    })

                # Update metrics
                metrics = self.metrics[conversation_id]
                metrics.total_turns += 1
                metrics.agent_participation[agent_slug] = metrics.agent_participation.get(agent_slug, 0) + 1
                metrics.total_duration += turn.duration

                # Release turn
                turn_manager = self.turn_managers[conversation_id]
                await turn_manager.release_turn(agent_participant["agentId"])

                # Determine if conversation should continue
                await self._evaluate_conversation_continuation(conversation_id, response, websocket_callback)

        except Exception as e:
            coordination_logger.error(f"Error processing turn for {agent_slug}: {e}")
            # Mark turn as failed
            turn.completedAt = datetime.now()
            turn.duration = (turn.completedAt - turn.startedAt).total_seconds()

            if websocket_callback:
                await websocket_callback({
                    "type": "agent_turn_failed",
                    "conversationId": conversation_id,
                    "agent": agent_participant,
                    "error": str(e)
                })

    async def _evaluate_conversation_continuation(
        self,
        conversation_id: str,
        last_response: str,
        websocket_callback: Optional[Callable] = None
    ):
        """Evaluate if conversation should continue with other agents"""
        session = self.active_conversations[conversation_id]
        rules = self.conversation_rules[conversation_id]

        # Simple continuation logic (can be enhanced with LLM)
        should_continue = (
            len(session.turns) < rules.max_participants and
            "다른 전문가" in last_response or "다른 에이전트" in last_response or
            "specialist" in last_response.lower() or
            "delegate" in last_response.lower()
        )

        if should_continue:
            # Select next agent
            current_agent_slugs = [turn.agentSlug for turn in session.turns]
            available_agents = [
                p for p in session.context["participants"]
                if p["agentSlug"] not in current_agent_slugs
            ]

            if available_agents:
                next_agent = available_agents[0]  # Simple selection

                # Send agent switch event
                if websocket_callback:
                    await websocket_callback({
                        "type": "conversation_continuation",
                        "conversationId": conversation_id,
                        "nextAgent": next_agent,
                        "reason": "automatic_continuation"
                    })

                # Process next turn
                await self._process_agent_turn(
                    conversation_id=conversation_id,
                    agent_participant=next_agent,
                    message=f"Previous response: {last_response}. Please provide additional assistance.",
                    websocket_callback=websocket_callback
                )
            else:
                # No more agents available - complete conversation
                await self.complete_conversation(conversation_id, "no_more_participants")
        else:
            # Conversation naturally completed
            await self.complete_conversation(conversation_id, "natural_completion")

    async def complete_conversation(self, conversation_id: str, reason: str = "completed"):
        """Complete conversation and cleanup"""
        if conversation_id not in self.active_conversations:
            return

        session = self.active_conversations[conversation_id]
        session.context["state"] = ConversationState.COMPLETED.value
        session.context["updatedAt"] = current_timestamp()
        session.context["metadata"]["completionReason"] = reason

        coordination_logger.info(f"Completing conversation {conversation_id}: {reason}")

        # Cleanup
        async with self._coordination_lock:
            if conversation_id in self.turn_managers:
                del self.turn_managers[conversation_id]
            if conversation_id in self.conversation_rules:
                del self.conversation_rules[conversation_id]

    def get_conversation_status(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed conversation status"""
        if conversation_id not in self.active_conversations:
            return None

        session = self.active_conversations[conversation_id]
        turn_manager = self.turn_managers.get(conversation_id)
        metrics = self.metrics.get(conversation_id)

        return {
            "conversation": session.to_dict(),
            "turnStatistics": turn_manager.get_turn_statistics() if turn_manager else {},
            "metrics": metrics.__dict__ if metrics else {},
            "active": session.context["state"] in [
                ConversationState.ACTIVE.value,
                ConversationState.STREAMING.value
            ]
        }

    def list_active_conversations(self) -> List[str]:
        """List all active conversation IDs"""
        return [
            conv_id for conv_id, session in self.active_conversations.items()
            if session.context["state"] in [
                ConversationState.ACTIVE.value,
                ConversationState.STREAMING.value
            ]
        ]


# Global instance
conversation_coordinator = ConversationCoordinator()


# Utility functions
async def start_multi_agent_conversation(
    topic: str,
    agent_slugs: List[str],
    initial_message: str,
    initiator_id: str = "user",
    rules: Optional[ConversationRule] = None,
    websocket_callback: Optional[Callable] = None
) -> Optional[str]:
    """
    Convenience function to start multi-agent conversation
    Returns conversation_id if successful
    """
    try:
        session = await conversation_coordinator.create_conversation(
            topic=topic,
            initiator_id=initiator_id,
            participant_agent_slugs=agent_slugs,
            rules=rules
        )

        conversation_id = session.context["conversationId"]
        success = await conversation_coordinator.start_conversation(
            conversation_id=conversation_id,
            initial_message=initial_message,
            websocket_callback=websocket_callback
        )

        return conversation_id if success else None
    except Exception as e:
        logger.error(f"Failed to start multi-agent conversation: {e}")
        return None


async def get_conversation_summary(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Get conversation summary with key insights"""
    status = conversation_coordinator.get_conversation_status(conversation_id)
    if not status:
        return None

    conversation = status["conversation"]
    turns = conversation["turns"]

    # Generate summary
    summary = {
        "conversationId": conversation_id,
        "topic": conversation["context"]["topic"],
        "duration": status["turnStatistics"].get("totalDuration", 0),
        "totalTurns": len(turns),
        "participants": [p["agentName"] for p in conversation["context"]["participants"]],
        "keyMessages": [turn["message"]["parts"][0]["text"][:100] + "..." for turn in turns[:3]],
        "state": conversation["context"]["state"],
        "metrics": status["metrics"]
    }

    return summary