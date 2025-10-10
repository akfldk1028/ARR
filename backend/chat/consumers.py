"""
Chat WebSocket Consumer with A2A Integration
텍스트 채팅 전용 consumer로 A2A 라우팅 및 Neo4j 저장 포함
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from uuid import uuid4

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import StopConsumer
from asgiref.sync import sync_to_async

# Django models
from gemini.models import ChatSession, ChatMessage

# A2A Worker Agent System (agents/ 구현 참조)
from agents.worker_agents.worker_manager import WorkerAgentManager
from graph_db.services import get_neo4j_service
from graph_db.tracking import ConversationTracker, TaskManager, ProvenanceTracker

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """
    텍스트 채팅 전용 WebSocket Consumer
    - A2A 라우팅 자동 적용
    - Neo4j 대화 저장
    - 의미론적 분석으로 전문 에이전트 자동 위임
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.browser_session_id = None  # Django HTTP session ID (browser connection)
        self.chat_session = None
        self.user_obj = None
        self.worker_manager = WorkerAgentManager()
        self.current_agent_slug = "hostagent"  # Host Agent (조정자)

        # Neo4j Integration
        self.neo4j_service = get_neo4j_service()
        self.conversation_tracker = ConversationTracker(self.neo4j_service)
        self.task_manager = TaskManager(self.neo4j_service)
        self.provenance_tracker = ProvenanceTracker(self.neo4j_service)
        self.conversation_id = None  # Neo4j conversation tracking ID
        self.turn_counter = 0  # Turn counter for this session

        self.a2a_handler = None  # A2A Handler (connect 시 초기화)

    # ============== CONNECTION MANAGEMENT ==============

    async def connect(self):
        """WebSocket 연결 초기화"""
        try:
            await self.accept()

            # 사용자 및 Django 세션 초기화
            self.user_obj = await self._get_user()
            self.chat_session = await self._get_or_create_session()
            self.browser_session_id = str(self.chat_session.id)

            # Neo4j Conversation 생성 (WebSocket 연결마다 새 대화)
            username = self.user_obj.username if self.user_obj else 'anonymous'
            self.conversation_id = self.conversation_tracker.create_conversation(
                username,
                metadata={'django_session_id': self.browser_session_id, 'agent': self.current_agent_slug}
            )

            # Initialize turn_counter from last Turn in this Conversation
            self.turn_counter = self.conversation_tracker.get_last_turn_sequence(self.conversation_id)
            logger.info(f"Conversation ready: {self.conversation_id}, starting from Turn {self.turn_counter}")

            # Gemini service는 없으므로 None 설정 (A2A Handler 초기화 전에 먼저 설정)
            self.gemini_service = None

            # A2A Handler 초기화 (gemini/simple_consumer.py와 동일)
            from gemini.consumers.handlers.a2a_handler import A2AHandler
            self.a2a_handler = A2AHandler(self)

            await self._send_welcome_message()
            logger.info(f"Chat connected: Browser={self.browser_session_id[:16]}..., Conversation={self.conversation_id[:16]}...")

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            await self._send_error(f"Connection failed: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        """연결 종료"""
        try:
            if self.chat_session:
                await self._update_session_activity()
            logger.info(f"Chat disconnected: Browser={self.browser_session_id[:16] if self.browser_session_id else 'N/A'}...")
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
        finally:
            raise StopConsumer()

    # ============== MESSAGE ROUTING ==============

    async def receive(self, text_data):
        """수신 메시지 라우팅"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            logger.info(f"Received: {message_type}")

            # 메시지 타입별 핸들러
            handlers = {
                'chat_message': self._handle_chat_message,
                'switch_agent': self._handle_agent_switch,
                'list_agents': self._handle_list_agents,
                'session_info': self._handle_session_info,
                'history': self._handle_history,
            }

            handler = handlers.get(message_type)
            if handler:
                await handler(data)
            else:
                await self._send_error(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            await self._send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Message processing error: {e}")
            await self._send_error(f"Processing error: {str(e)}")

    # ============== CORE A2A INTEGRATION ==============

    async def _handle_chat_message(self, data):
        """
        텍스트 메시지 처리

        general_worker(Host Agent)가 자동으로:
        1. Semantic routing (agent_discovery.py)
        2. LLM 응답 생성
        3. 필요시 specialist delegation
        """
        try:
            # A2A Handler가 general_worker로 전달
            # general_worker 내부에서 semantic routing + delegation 자동 처리
            await self.a2a_handler.handle_text(data)

        except Exception as e:
            logger.error(f"Chat message processing failed: {e}")
            await self._send_error(f"Chat processing failed: {str(e)}")

    # ============== OTHER MESSAGE HANDLERS ==============

    async def _handle_agent_switch(self, data):
        """에이전트 수동 전환"""
        try:
            new_agent_slug = data.get('agent_slug')
            if not new_agent_slug:
                await self._send_error("Agent slug is required")
                return

            agent = await self.worker_manager.get_worker(new_agent_slug)
            if not agent:
                await self._send_error(f"Agent '{new_agent_slug}' not found")
                return

            old_agent = self.current_agent_slug
            self.current_agent_slug = new_agent_slug

            await self.send(text_data=json.dumps({
                'type': 'agent_switched',
                'old_agent': old_agent,
                'new_agent': new_agent_slug,
                'agent_name': agent.agent_name,
                'success': True
            }))

        except Exception as e:
            await self._send_error(f"Failed to switch agent: {str(e)}")

    async def _handle_list_agents(self, data):
        """사용 가능한 에이전트 목록"""
        try:
            agents = {
                "general-worker": {
                    "name": "General Assistant",
                    "description": "일반 대화 및 질문 응답"
                },
                "flight-specialist": {
                    "name": "Flight Specialist",
                    "description": "항공편 검색 및 예약 전문가"
                }
            }

            await self.send(text_data=json.dumps({
                'type': 'agents_list',
                'current_agent': self.current_agent_slug,
                'agents': agents,
                'success': True
            }))

        except Exception as e:
            await self._send_error(f"Failed to list agents: {str(e)}")

    async def _handle_session_info(self, data):
        """세션 정보 전송"""
        try:
            message_count = await self._get_message_count()
            await self.send(text_data=json.dumps({
                'type': 'session_info',
                'browser_session_id': self.browser_session_id,
                'conversation_id': self.conversation_id,
                'user': self.user_obj.username if self.user_obj else 'Anonymous',
                'current_agent': self.current_agent_slug,
                'message_count': message_count,
                'success': True
            }))
        except Exception as e:
            await self._send_error(f"Failed to get session info: {str(e)}")

    async def _handle_history(self, data):
        """대화 기록 전송"""
        try:
            limit = min(data.get('limit', 50), 100)
            messages = await self._get_recent_messages(limit)
            await self.send(text_data=json.dumps({
                'type': 'history',
                'messages': messages,
                'count': len(messages),
                'success': True
            }))
        except Exception as e:
            await self._send_error(f"Failed to get history: {str(e)}")

    # ============== UTILITY METHODS ==============

    async def _get_user(self):
        """인증된 사용자 가져오기"""
        user = self.scope.get("user")
        return user if user and user.is_authenticated else None

    async def _send_welcome_message(self):
        """환영 메시지 전송"""
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'message': 'Connected to A2A Chat System',
            'browser_session_id': self.browser_session_id,
            'conversation_id': self.conversation_id,
            'user': self.user_obj.username if self.user_obj else 'Anonymous',
            'current_agent': self.current_agent_slug,
            'success': True
        }))

    async def _send_error(self, message: str):
        """에러 응답 전송"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'success': False
        }))

    # ============== DATABASE OPERATIONS ==============

    async def _get_or_create_session(self):
        """채팅 세션 생성 (WebSocket 연결마다 새 세션)"""
        from django.utils import timezone

        # 기존 활성 세션 비활성화 (새로고침/재연결 시)
        try:
            old_session = await sync_to_async(ChatSession.objects.get)(
                user=self.user_obj,
                is_active=True
            )
            old_session.is_active = False
            await sync_to_async(old_session.save)()
            logger.info(f"Deactivated old session {old_session.id}")
        except ChatSession.DoesNotExist:
            pass

        # 항상 새 세션 생성
        return await sync_to_async(ChatSession.objects.create)(
            user=self.user_obj,
            is_active=True,
            title=f"Chat {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            metadata={'system': 'a2a_chat'}
        )

    async def _save_message(self, content: str, message_type: str, sender_type: str, metadata=None):
        """메시지 저장"""
        message = await sync_to_async(ChatMessage.objects.create)(
            session=self.chat_session,
            content=content,
            message_type=message_type,
            sender_type=sender_type,
            metadata=metadata or {}
        )
        return message

    async def _get_message_count(self):
        """메시지 개수 조회"""
        return await sync_to_async(self.chat_session.messages.count)()

    async def _get_recent_messages(self, limit: int):
        """최근 메시지 조회"""
        def get_messages():
            messages = self.chat_session.messages.select_related().order_by('-created_at')[:limit]
            return [
                {
                    'id': str(msg.id),
                    'content': msg.content,
                    'message_type': msg.message_type,
                    'sender_type': msg.sender_type,
                    'created_at': msg.created_at.isoformat(),
                    'metadata': msg.metadata
                }
                for msg in reversed(messages)
            ]

        return await sync_to_async(get_messages)()

    async def _update_session_activity(self):
        """세션 활동 시간 업데이트"""
        from django.utils import timezone
        if self.chat_session:
            await sync_to_async(ChatSession.objects.filter(id=self.chat_session.id).update)(
                updated_at=timezone.now()
            )
