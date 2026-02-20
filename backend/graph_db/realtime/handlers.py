"""
Neo4j Event Handlers
Separated for better modularity and testability
"""
import logging
from typing import Dict, Any, Optional
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


class BaseEventHandler:
    """Base class for event handlers"""

    def __init__(self):
        self.channel_layer = get_channel_layer()

    async def broadcast_to_group(
        self,
        group_name: str,
        event_type: str,
        data: Dict[str, Any]
    ):
        """
        Broadcast event to a Django Channels group

        Args:
            group_name: Name of the group to broadcast to
            event_type: Type of the event
            data: Event data
        """
        await self.channel_layer.group_send(
            group_name,
            {
                'type': 'neo4j_event',
                'event_type': event_type,
                'data': data
            }
        )
        logger.debug("[BROADCAST] Broadcasted %s to %s", event_type, group_name)


class ConversationEventHandler(BaseEventHandler):
    """Handler for Conversation-related events"""

    async def handle_created(self, data: Dict[str, Any]):
        """
        Handle conversation created event

        Args:
            data: Event data with django_session_id, conversation_id, etc.
        """
        django_session_id = data.get('django_session_id')
        conversation_id = data.get('conversation_id')

        if not django_session_id:
            logger.warning("[WARNING] conversation_created missing django_session_id")
            return

        group_name = f"chat_{django_session_id}"
        await self.broadcast_to_group(group_name, 'conversation_created', data)

        logger.info(
            "[OK] conversation_created (id=%s) -> %s",
            conversation_id[:16] if conversation_id else 'N/A',
            group_name
        )

    async def handle_updated(self, data: Dict[str, Any]):
        """
        Handle conversation updated event

        Args:
            data: Event data with conversation_id, updated fields, etc.
        """
        conversation_id = data.get('conversation_id')

        if not conversation_id:
            logger.warning("[WARNING] conversation_updated missing conversation_id")
            return

        group_name = f"conversation_{conversation_id}"
        await self.broadcast_to_group(group_name, 'conversation_updated', data)

        logger.info("[OK] conversation_updated -> %s", group_name)


class MessageEventHandler(BaseEventHandler):
    """Handler for Message-related events"""

    async def handle_created(self, data: Dict[str, Any]):
        """
        Handle message created event

        Args:
            data: Event data with message_id, conversation_id, content, etc.
        """
        conversation_id = data.get('conversation_id')
        message_id = data.get('message_id')
        role = data.get('role', 'unknown')

        if not conversation_id:
            logger.warning("[WARNING] message_created missing conversation_id")
            return

        group_name = f"conversation_{conversation_id}"
        await self.broadcast_to_group(group_name, 'message_created', data)

        logger.info(
            "[OK] message_created [%s] (id=%s) -> %s",
            role,
            message_id[:16] if message_id else 'N/A',
            group_name
        )


class TurnEventHandler(BaseEventHandler):
    """Handler for Turn-related events"""

    async def handle_created(self, data: Dict[str, Any]):
        """
        Handle turn created event

        Args:
            data: Event data with turn_id, conversation_id, sequence, etc.
        """
        conversation_id = data.get('conversation_id')
        turn_id = data.get('turn_id')
        sequence = data.get('sequence', 'N/A')

        if not conversation_id:
            logger.warning("[WARNING] turn_created missing conversation_id")
            return

        group_name = f"conversation_{conversation_id}"
        await self.broadcast_to_group(group_name, 'turn_created', data)

        logger.info(
            "[OK] turn_created (seq=%s, id=%s) -> %s",
            sequence,
            turn_id[:16] if turn_id else 'N/A',
            group_name
        )


class AgentExecutionEventHandler(BaseEventHandler):
    """Handler for AgentExecution-related events"""

    async def handle_created(self, data: Dict[str, Any]):
        """
        Handle agent execution created event

        Args:
            data: Event data with execution_id, agent_slug, turn_id, etc.
        """
        turn_id = data.get('turn_id')
        agent_slug = data.get('agent_slug', 'unknown')
        execution_id = data.get('execution_id')

        if not turn_id:
            logger.warning("[WARNING] agent_execution_created missing turn_id")
            return

        group_name = f"turn_{turn_id}"
        await self.broadcast_to_group(group_name, 'agent_execution_created', data)

        logger.info(
            "[OK] agent_execution_created [%s] (id=%s) -> %s",
            agent_slug,
            execution_id[:16] if execution_id else 'N/A',
            group_name
        )

    async def handle_completed(self, data: Dict[str, Any]):
        """
        Handle agent execution completed event

        Args:
            data: Event data with execution_id, status, execution_time_ms, etc.
        """
        execution_id = data.get('execution_id')
        status = data.get('status', 'completed')
        execution_time_ms = data.get('execution_time_ms')

        if not execution_id:
            logger.warning("[WARNING] agent_execution_completed missing execution_id")
            return

        group_name = f"execution_{execution_id}"
        await self.broadcast_to_group(group_name, 'agent_execution_completed', data)

        logger.info(
            "[OK] agent_execution_completed [%s] (time=%sms) -> %s",
            status,
            execution_time_ms or 'N/A',
            group_name
        )


class EventHandlerRegistry:
    """
    Registry for event handlers
    Makes it easy to add/modify handlers without changing listener code
    """

    def __init__(self):
        self.conversation = ConversationEventHandler()
        self.message = MessageEventHandler()
        self.turn = TurnEventHandler()
        self.agent_execution = AgentExecutionEventHandler()

    async def route_event(self, channel: str, data: Dict[str, Any]):
        """
        Route event to appropriate handler

        Args:
            channel: Redis channel name
            data: Event data

        Raises:
            ValueError: If channel is unknown
        """
        routing_map = {
            'neo4j:conversation:created': self.conversation.handle_created,
            'neo4j:conversation:updated': self.conversation.handle_updated,
            'neo4j:message:created': self.message.handle_created,
            'neo4j:turn:created': self.turn.handle_created,
            'neo4j:agent_execution:created': self.agent_execution.handle_created,
            'neo4j:agent_execution:completed': self.agent_execution.handle_completed,
        }

        handler = routing_map.get(channel)

        if handler:
            await handler(data)
        else:
            logger.warning("[WARNING] Unknown channel: %s", channel)
