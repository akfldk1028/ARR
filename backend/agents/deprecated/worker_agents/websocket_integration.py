"""
WebSocket Integration for Agent-to-Agent Conversations
Extends existing WebSocket consumer with A2A conversation capabilities
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List

from .conversation_coordinator import (
    conversation_coordinator, ConversationRule,
    start_multi_agent_conversation, get_conversation_summary
)
from .a2a_streaming import conversation_streamer
from .conversation_types import ConversationState

logger = logging.getLogger('agents.websocket_integration')


class A2AWebSocketMixin:
    """
    Mixin to add A2A conversation capabilities to WebSocket consumers
    To be mixed into SimpleChatConsumer
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A2A Conversation state
        self.active_conversations: Dict[str, str] = {}  # conversation_id -> state
        self.conversation_mode = False
        self.current_conversation_id: Optional[str] = None

    async def _handle_start_multi_agent_conversation(self, data: Dict[str, Any]):
        """Start multi-agent conversation"""
        try:
            agent_slugs = data.get('agent_slugs', [])
            topic = data.get('topic', 'General discussion')
            initial_message = data.get('message', 'Let\'s start our conversation.')

            if not agent_slugs or len(agent_slugs) < 2:
                await self._send_error("At least 2 agents required for conversation")
                return

            logger.info(f"Starting multi-agent conversation with agents: {agent_slugs}")

            # Create conversation rules
            rules = ConversationRule(
                max_participants=len(agent_slugs),
                max_turn_duration=120,
                max_conversation_duration=1800,
                auto_escalation=True,
                allow_interruption=data.get('allow_interruption', True)
            )

            # Create websocket callback for real-time updates
            async def websocket_callback(event_data):
                await self.send(text_data=json.dumps({
                    'type': 'multi_agent_event',
                    'event': event_data,
                    'timestamp': time.time()
                }))

            # Start conversation
            conversation_id = await start_multi_agent_conversation(
                topic=topic,
                agent_slugs=agent_slugs,
                initial_message=initial_message,
                initiator_id=self.user_obj.username if self.user_obj else "user",
                rules=rules,
                websocket_callback=websocket_callback
            )

            if conversation_id:
                self.active_conversations[conversation_id] = ConversationState.ACTIVE.value
                self.current_conversation_id = conversation_id
                self.conversation_mode = True

                await self.send(text_data=json.dumps({
                    'type': 'multi_agent_conversation_started',
                    'conversation_id': conversation_id,
                    'topic': topic,
                    'participants': agent_slugs,
                    'success': True
                }))

                logger.info(f"Multi-agent conversation started: {conversation_id}")
            else:
                await self._send_error("Failed to start multi-agent conversation")

        except Exception as e:
            logger.error(f"Error starting multi-agent conversation: {e}")
            await self._send_error(f"Conversation start failed: {str(e)}")

    async def _handle_join_conversation(self, data: Dict[str, Any]):
        """Join existing conversation as observer or participant"""
        try:
            conversation_id = data.get('conversation_id')
            if not conversation_id:
                await self._send_error("Conversation ID required")
                return

            # Check if conversation exists
            status = conversation_coordinator.get_conversation_status(conversation_id)
            if not status:
                await self._send_error("Conversation not found")
                return

            # Join as observer
            self.current_conversation_id = conversation_id
            self.conversation_mode = True
            self.active_conversations[conversation_id] = ConversationState.ACTIVE.value

            await self.send(text_data=json.dumps({
                'type': 'conversation_joined',
                'conversation_id': conversation_id,
                'status': status,
                'success': True
            }))

            logger.info(f"User joined conversation: {conversation_id}")

        except Exception as e:
            logger.error(f"Error joining conversation: {e}")
            await self._send_error(f"Failed to join conversation: {str(e)}")

    async def _handle_leave_conversation(self, data: Dict[str, Any]):
        """Leave current conversation"""
        try:
            conversation_id = data.get('conversation_id') or self.current_conversation_id

            if conversation_id and conversation_id in self.active_conversations:
                del self.active_conversations[conversation_id]

                if self.current_conversation_id == conversation_id:
                    self.current_conversation_id = None
                    self.conversation_mode = False

                await self.send(text_data=json.dumps({
                    'type': 'conversation_left',
                    'conversation_id': conversation_id,
                    'success': True
                }))

                logger.info(f"User left conversation: {conversation_id}")
            else:
                await self._send_error("Not in any conversation")

        except Exception as e:
            logger.error(f"Error leaving conversation: {e}")
            await self._send_error(f"Failed to leave conversation: {str(e)}")

    async def _handle_list_conversations(self, data: Dict[str, Any]):
        """List active conversations"""
        try:
            active_conversations = conversation_coordinator.list_active_conversations()

            conversation_list = []
            for conv_id in active_conversations:
                status = conversation_coordinator.get_conversation_status(conv_id)
                if status:
                    summary = {
                        'conversation_id': conv_id,
                        'topic': status['conversation']['context']['topic'],
                        'state': status['conversation']['context']['state'],
                        'participants': [
                            p['agentName'] for p in status['conversation']['context']['participants']
                        ],
                        'turn_count': len(status['conversation']['turns']),
                        'created_at': status['conversation']['context']['createdAt']
                    }
                    conversation_list.append(summary)

            await self.send(text_data=json.dumps({
                'type': 'conversations_list',
                'conversations': conversation_list,
                'user_current_conversation': self.current_conversation_id,
                'success': True
            }))

        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            await self._send_error(f"Failed to list conversations: {str(e)}")

    async def _handle_conversation_status(self, data: Dict[str, Any]):
        """Get conversation status and history"""
        try:
            conversation_id = data.get('conversation_id') or self.current_conversation_id

            if not conversation_id:
                await self._send_error("No conversation specified")
                return

            status = conversation_coordinator.get_conversation_status(conversation_id)
            if not status:
                await self._send_error("Conversation not found")
                return

            await self.send(text_data=json.dumps({
                'type': 'conversation_status',
                'conversation_id': conversation_id,
                'status': status,
                'success': True
            }))

        except Exception as e:
            logger.error(f"Error getting conversation status: {e}")
            await self._send_error(f"Failed to get conversation status: {str(e)}")

    async def _handle_send_to_conversation(self, data: Dict[str, Any]):
        """Send message to specific agent in conversation"""
        try:
            conversation_id = data.get('conversation_id') or self.current_conversation_id
            target_agent = data.get('target_agent')
            message = data.get('message', '').strip()

            if not conversation_id:
                await self._send_error("No active conversation")
                return

            if not target_agent:
                await self._send_error("Target agent required")
                return

            if not message:
                await self._send_error("Message cannot be empty")
                return

            # Get conversation status
            status = conversation_coordinator.get_conversation_status(conversation_id)
            if not status:
                await self._send_error("Conversation not found")
                return

            # Find target agent in participants
            participants = status['conversation']['context']['participants']
            target_participant = None
            for p in participants:
                if p['agentSlug'] == target_agent or p['agentId'] == target_agent:
                    target_participant = p
                    break

            if not target_participant:
                await self._send_error(f"Agent {target_agent} not found in conversation")
                return

            # Create websocket callback for updates
            async def websocket_callback(event_data):
                await self.send(text_data=json.dumps({
                    'type': 'conversation_message_response',
                    'conversation_id': conversation_id,
                    'target_agent': target_agent,
                    'event': event_data,
                    'timestamp': time.time()
                }))

            # Process agent turn
            await conversation_coordinator._process_agent_turn(
                conversation_id=conversation_id,
                agent_participant=target_participant,
                message=message,
                websocket_callback=websocket_callback
            )

            await self.send(text_data=json.dumps({
                'type': 'conversation_message_sent',
                'conversation_id': conversation_id,
                'target_agent': target_agent,
                'message': message,
                'success': True
            }))

        except Exception as e:
            logger.error(f"Error sending to conversation: {e}")
            await self._send_error(f"Failed to send message: {str(e)}")

    async def _handle_stop_conversation(self, data: Dict[str, Any]):
        """Stop active conversation"""
        try:
            conversation_id = data.get('conversation_id') or self.current_conversation_id

            if not conversation_id:
                await self._send_error("No conversation to stop")
                return

            # Complete conversation
            await conversation_coordinator.complete_conversation(
                conversation_id,
                reason="user_requested_stop"
            )

            # Remove from active conversations
            if conversation_id in self.active_conversations:
                del self.active_conversations[conversation_id]

            if self.current_conversation_id == conversation_id:
                self.current_conversation_id = None
                self.conversation_mode = False

            await self.send(text_data=json.dumps({
                'type': 'conversation_stopped',
                'conversation_id': conversation_id,
                'success': True
            }))

            logger.info(f"Conversation stopped: {conversation_id}")

        except Exception as e:
            logger.error(f"Error stopping conversation: {e}")
            await self._send_error(f"Failed to stop conversation: {str(e)}")

    async def _handle_get_conversation_summary(self, data: Dict[str, Any]):
        """Get conversation summary"""
        try:
            conversation_id = data.get('conversation_id') or self.current_conversation_id

            if not conversation_id:
                await self._send_error("No conversation specified")
                return

            summary = await get_conversation_summary(conversation_id)
            if not summary:
                await self._send_error("Conversation not found or no summary available")
                return

            await self.send(text_data=json.dumps({
                'type': 'conversation_summary',
                'conversation_id': conversation_id,
                'summary': summary,
                'success': True
            }))

        except Exception as e:
            logger.error(f"Error getting conversation summary: {e}")
            await self._send_error(f"Failed to get conversation summary: {str(e)}")

    def get_a2a_message_handlers(self) -> Dict[str, Any]:
        """Get A2A message handlers for integration with main consumer"""
        return {
            # Multi-agent conversation handlers
            'start_multi_agent_conversation': self._handle_start_multi_agent_conversation,
            'join_conversation': self._handle_join_conversation,
            'leave_conversation': self._handle_leave_conversation,
            'list_conversations': self._handle_list_conversations,
            'conversation_status': self._handle_conversation_status,
            'send_to_conversation': self._handle_send_to_conversation,
            'stop_conversation': self._handle_stop_conversation,
            'get_conversation_summary': self._handle_get_conversation_summary,
        }

    async def cleanup_conversations(self):
        """Cleanup conversations on disconnect"""
        if self.current_conversation_id:
            try:
                await conversation_coordinator.complete_conversation(
                    self.current_conversation_id,
                    reason="user_disconnected"
                )
            except Exception as e:
                logger.warning(f"Error cleaning up conversation {self.current_conversation_id}: {e}")

        self.active_conversations.clear()
        self.current_conversation_id = None
        self.conversation_mode = False


# Enhanced SimpleChatConsumer with A2A capabilities
class EnhancedSimpleChatConsumer(A2AWebSocketMixin):
    """
    Enhanced WebSocket Consumer with A2A conversation capabilities
    This class extends the basic consumer with multi-agent conversation support
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Additional A2A specific initialization

    async def receive(self, text_data):
        """Enhanced receive method with A2A message handling"""
        try:
            # Parse JSON once and cache
            data = json.loads(text_data)
            message_type = data.get('type')

            logger.info(f"WebSocket received message: type={message_type}")

            # Get A2A handlers
            a2a_handlers = self.get_a2a_message_handlers()

            # Check if it's an A2A message type
            if message_type in a2a_handlers:
                handler = a2a_handlers[message_type]
                await handler(data)
                return

            # Fall back to original handler logic
            # (This would be integrated into the actual SimpleChatConsumer)
            await self._handle_original_message_types(data)

        except json.JSONDecodeError:
            await self._send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Message processing error: {e}")
            await self._send_error(f"Processing error: {str(e)}")

    async def _handle_original_message_types(self, data: Dict[str, Any]):
        """Placeholder for original message handling"""
        # This would call the original SimpleChatConsumer message handlers
        message_type = data.get('type')

        # Basic handlers for compatibility
        if message_type == 'session_info':
            await self._handle_session_info()
        elif message_type == 'list_agents':
            await self._handle_list_agents()
        else:
            await self._send_error(f"Unsupported message type: {message_type}")

    async def _handle_session_info(self):
        """Basic session info handler"""
        await self.send(text_data=json.dumps({
            'type': 'session_info',
            'session_id': getattr(self, 'session_id', 'unknown'),
            'conversation_mode': self.conversation_mode,
            'current_conversation': self.current_conversation_id,
            'active_conversations': len(self.active_conversations),
            'success': True
        }))

    async def _handle_list_agents(self):
        """Basic agent list handler"""
        # This would integrate with the original agent list functionality
        available_agents = {
            "general-worker": {
                "name": "General Assistant",
                "description": "General-purpose AI assistant",
                "capabilities": ["text", "conversation", "coordination"]
            },
            "flight-specialist": {
                "name": "Flight Specialist",
                "description": "Flight booking and travel specialist",
                "capabilities": ["flight_booking", "travel_info"]
            }
        }

        await self.send(text_data=json.dumps({
            'type': 'agents_list',
            'agents': available_agents,
            'current_agent': getattr(self, 'current_agent_slug', 'general-worker'),
            'conversation_mode': self.conversation_mode,
            'success': True
        }))

    async def disconnect(self, close_code):
        """Enhanced disconnect with A2A cleanup"""
        try:
            # Cleanup conversations
            await self.cleanup_conversations()

            # Original disconnect logic would go here
            logger.info(f"Enhanced chat session ended with A2A cleanup")

        except Exception as e:
            logger.error(f"Disconnect error: {e}")

    async def _send_error(self, message: str):
        """Send error response"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'success': False
        }))


# Integration instructions for existing SimpleChatConsumer
INTEGRATION_INSTRUCTIONS = """
To integrate A2A capabilities into existing SimpleChatConsumer:

1. Add A2AWebSocketMixin as a parent class:
   class SimpleChatConsumer(A2AWebSocketMixin, AsyncWebsocketConsumer):

2. Update the receive method to include A2A handlers:
   async def receive(self, text_data):
       # ... existing JSON parsing ...

       # Add A2A handler check
       a2a_handlers = self.get_a2a_message_handlers()
       if message_type in a2a_handlers:
           handler = a2a_handlers[message_type]
           await handler(data)
           return

       # ... existing message handlers ...

3. Update disconnect method:
   async def disconnect(self, close_code):
       try:
           await self.cleanup_conversations()
           # ... existing disconnect logic ...

4. The enhanced consumer supports these new message types:
   - start_multi_agent_conversation
   - join_conversation
   - leave_conversation
   - list_conversations
   - conversation_status
   - send_to_conversation
   - stop_conversation
   - get_conversation_summary
"""