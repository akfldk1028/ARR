"""
Optimized Live API + A2A Worker Bridge
Clean separation of concerns with enhanced performance
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass

from agents.worker_agents.worker_manager import WorkerAgentManager
from agents.worker_agents.agent_discovery import AgentDiscoveryService
from gemini.services.websocket_live_client import ContinuousVoiceSession
from config.agent_config import AgentConfig

logger = logging.getLogger(__name__)


@dataclass
class LiveA2ARequest:
    """Clean request structure"""
    user_input: str
    user_id: str
    session_id: str
    voice_preference: str = "Aoede"
    context: Dict[str, Any] = None


@dataclass
class LiveA2AResponse:
    """Clean response structure"""
    success: bool
    response_text: str
    agent_slug: str
    agent_name: str
    delegation_occurred: bool = False
    delegated_agent: Optional[str] = None
    specialist_response: Optional[str] = None
    handoff_message: Optional[str] = None
    voice_name: Optional[str] = None
    processing_time: float = 0.0
    error_message: Optional[str] = None


class OptimizedLiveA2ABridge:
    """
    Optimized bridge between Live API and A2A Workers

    Flow:
    1. Live API transcript ??Delegate check ??A2A process ??TTS response
    2. Direct integration with simplified routing logic
    """

        HANDOFF_CONFIRMATION_MESSAGE = (
        "\ub124\uc54c\uacb0\uc2b5\ub2c8\ub2e4\ube44\ud589\uae30\uc5d0\uc774\uc804\ud2b8\ub97c\ud1b5\ud574\uc608\uc57d\ud558\uaca0\uc2b5\ub2c8\ub2e4"
    )        self.voice_session: Optional[ContinuousVoiceSession] = None

        # Performance tracking
        self.request_count = 0
        self.total_processing_time = 0.0

    async def initialize(self, api_key: str, voice_callback: Callable = None):
        """Initialize the bridge with Live API connection"""
        try:
            # Initialize voice session
            self.voice_session = ContinuousVoiceSession(api_key)

            # Initialize discovery service
            agent = await self.worker_manager.get_worker(self.current_agent)
            if agent and hasattr(agent, 'llm'):
                self.discovery_service = AgentDiscoveryService(agent.llm)

            logger.info("OptimizedLiveA2ABridge initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Bridge initialization failed: {e}")
            return False

    async def process_live_transcript(self, transcript: str, user_id: str, session_id: str) -> LiveA2AResponse:
        """
        Core processing method: Live API transcript ??A2A routing ??Response

        This is the main bridge method that handles:
        1. Input validation
        2. Delegation decision
        3. A2A processing
        4. Response preparation
        """
        start_time = time.time()
        self.request_count += 1

        try:
            # Input validation
            if not transcript or len(transcript.strip()) < 2:
                return LiveA2AResponse(
                    success=False,
                    response_text="",
                    agent_slug=self.current_agent,
                    agent_name="System",
                    error_message="Empty or too short transcript"
                )

            request = LiveA2ARequest(
                user_input=transcript.strip(),
                user_id=user_id,
                session_id=session_id
            )

            # Check if delegation is needed
            should_delegate, target_agent = await self._should_delegate(request.user_input)

            if should_delegate and target_agent:
                # Delegate to specialist
                response = await self._process_with_specialist(request, target_agent)
            else:
                # Process with current agent
                response = await self._process_with_current_agent(request)

            # Update performance metrics
            processing_time = time.time() - start_time
            self.total_processing_time += processing_time
            response.processing_time = processing_time

            logger.info(f"Bridge processed request in {processing_time:.2f}s - Delegation: {should_delegate}")
            return response

        except Exception as e:
            logger.error(f"Bridge processing failed: {e}")
            return LiveA2AResponse(
                success=False,
                response_text="Processing failed",
                agent_slug=self.current_agent,
                agent_name="System",
                processing_time=time.time() - start_time,
                error_message=str(e)
            )

    async def _should_delegate(self, user_input: str) -> tuple[bool, Optional[str]]:
        """Simplified delegation check"""
        try:
            if not self.discovery_service:
                return False, None

            should_delegate, target_agent = await self.discovery_service.should_delegate_request(
                user_request=user_input,
                current_agent_slug=self.current_agent
            )

            logger.info(f"Delegation check: {should_delegate} ??{target_agent}")
            return should_delegate, target_agent

        except Exception as e:
            logger.error(f"Delegation check failed: {e}")
            return False, None

    async def _process_with_specialist(self, request: LiveA2ARequest, target_agent: str) -> LiveA2AResponse:
        """Process request with specialist agent"""
        try:
            specialist = await self.worker_manager.get_worker(target_agent)
            if not specialist:
                raise Exception(f"Specialist agent '{target_agent}' not found")

            handoff_message = None
            specialist_input = request.user_input
            specialist_voice = AgentConfig.get_voice_for_agent(target_agent)

            if target_agent == 'flight-specialist':
                handoff_message = self.HANDOFF_CONFIRMATION_MESSAGE
                specialist_input = f"{handoff_message}\n\n\uc6d0\ubcf8 \uc0ac\uc6a9\uc790 \uc694\uccad: {request.user_input}\"
                logger.info('Forwarding Live API confirmation to flight specialist')

            specialist_response_text = await specialist.process_request(
                user_input=specialist_input,
                context_id=request.session_id,
                session_id=request.session_id,
                user_name=request.user_id
            )

            return LiveA2AResponse(
                success=True,
                response_text=specialist_response_text,
                agent_slug=target_agent,
                agent_name=specialist.agent_name,
                delegation_occurred=True,
                delegated_agent=target_agent,
                specialist_response=specialist_response_text,
                handoff_message=handoff_message,
                voice_name=specialist_voice
            )

        except Exception as e:
            logger.error(f"Specialist processing failed: {e}")
            return LiveA2AResponse(
                success=False,
                response_text=f"Specialist processing failed: {str(e)}",
                agent_slug=self.current_agent,
                agent_name="System",
                error_message=str(e)
            )

    async def _process_with_current_agent(self, request: LiveA2ARequest) -> LiveA2AResponse:
        """Process request with current agent"""
        try:
            agent = await self.worker_manager.get_worker(self.current_agent)
            if not agent:
                raise Exception(f"Current agent '{self.current_agent}' not found")

            response_text = await agent.process_request(
                user_input=request.user_input,
                context_id=request.session_id,
                session_id=request.session_id,
                user_name=request.user_id
            )

            current_voice = AgentConfig.get_voice_for_agent(self.current_agent)

            return LiveA2AResponse(
                success=True,
                response_text=response_text,
                agent_slug=self.current_agent,
                agent_name=agent.agent_name,
                delegation_occurred=False,
                voice_name=current_voice
            )

        except Exception as e:
            logger.error(f"Current agent processing failed: {e}")
            return LiveA2AResponse(
                success=False,
                response_text=f"Processing failed: {str(e)}",
                agent_slug=self.current_agent,
                agent_name="System",
                error_message=str(e)
            )

    async def send_response_to_live_api(self, response: LiveA2AResponse) -> bool:
        """Send A2A response back to Live API for TTS"""
        try:
            if not self.voice_session:
                logger.error("No active voice session")
                return False

            if not response.success:
                logger.warning("Response marked unsuccessful; skipping Live API send")
                return False

            sent = False
            current_voice = AgentConfig.get_voice_for_agent(self.current_agent)
            target_voice = response.voice_name or current_voice

            try:
                if response.handoff_message:
                    updated = await self.voice_session.update_voice(current_voice)
                    if not updated:
                        logger.warning(f"Voice update to {current_voice} failed before handoff message")
                    await self.voice_session.send_text(response.handoff_message, role='MODEL')
                    logger.info(f"Handoff message sent to Live API: {response.handoff_message[:50]}...")
                    sent = True

                if response.response_text:
                    if response.delegation_occurred and target_voice != current_voice:
                        updated = await self.voice_session.update_voice(target_voice)
                        if not updated:
                            logger.warning(f"Voice update to {target_voice} failed before delegated response")
                        else:
                            logger.info(f"Switched voice to {target_voice} for delegated response")
                    else:
                        updated = await self.voice_session.update_voice(target_voice)
                        if not updated:
                            logger.warning(f"Voice update to {target_voice} failed before response")

                    await self.voice_session.send_text(response.response_text, role='MODEL')
                    logger.info(f"Response sent to Live API: {response.response_text[:50]}...")
                    sent = True

            finally:
                if response.delegation_occurred:
                    await self.voice_session.update_voice(current_voice)

            if not sent:
                logger.warning("No response content available for Live API")

            return sent

        except Exception as e:
            logger.error(f"Failed to send response to Live API: {e}")
            return False

    async def start_voice_session(self, websocket_callback: Callable, voice_name: str = "Aoede") -> bool:
        """Start Live API voice session with A2A integration"""
        try:
            if not self.voice_session:
                logger.error("Voice session not initialized")
                return False

            # Enhanced callback that processes through A2A bridge
            async def enhanced_callback(data):
                """Process Live API callbacks through A2A bridge"""
                try:
                    # Handle transcript from user
                    if data.get('type') == 'transcript' and data.get('text'):
                        transcript = data.get('text', '').strip()

                        # Check for user transcript marker
                        if transcript.startswith('[USER]:'):
                            user_text = transcript[7:].strip()
                            logger.info(f"Processing user transcript via bridge: {user_text}")

                            # Process through A2A bridge
                            bridge_response = await self.process_live_transcript(
                                transcript=user_text,
                                user_id="voice_user",
                                session_id="voice_session"
                            )

                            # If delegation occurred, send specialist response back to Live API
                            if bridge_response.success and bridge_response.delegation_occurred:
                                await self.send_response_to_live_api(bridge_response)

                                # Notify frontend of delegation
                                await websocket_callback({
                                    'type': 'a2a_delegation_notification',
                                    'original_agent': self.current_agent,
                                    'specialist_agent': bridge_response.delegated_agent,
                                    'user_request': user_text,
                                    'handoff_message': bridge_response.handoff_message,
                                    'specialist_response': bridge_response.specialist_response
                                })

                            # Forward to original callback
                            await websocket_callback(data)
                        else:
                            # Regular AI response - forward as is
                            await websocket_callback(data)
                    else:
                        # Non-transcript data - forward as is
                        await websocket_callback(data)

                except Exception as e:
                    logger.error(f"Enhanced callback failed: {e}")
                    # Fallback - forward original data
                    await websocket_callback(data)

            # Start voice session with enhanced callback
            await self.voice_session.start(enhanced_callback, voice_name)
            logger.info("Live API voice session started with A2A integration")
            return True

        except Exception as e:
            logger.error(f"Failed to start voice session: {e}")
            return False

    async def stop_voice_session(self):
        """Stop the voice session"""
        try:
            if self.voice_session:
                await self.voice_session.stop()
                logger.info("Voice session stopped")
        except Exception as e:
            logger.error(f"Failed to stop voice session: {e}")

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get bridge performance statistics"""
        avg_time = self.total_processing_time / max(self.request_count, 1)
        return {
            'total_requests': self.request_count,
            'total_processing_time': self.total_processing_time,
            'average_processing_time': avg_time,
            'current_agent': self.current_agent
        }


# Global bridge instance
_bridge_instance: Optional[OptimizedLiveA2ABridge] = None


def get_bridge() -> OptimizedLiveA2ABridge:
    """Get or create global bridge instance"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = OptimizedLiveA2ABridge()
    return _bridge_instance


async def initialize_bridge(api_key: str) -> bool:
    """Initialize the global bridge instance"""
    bridge = get_bridge()
    return await bridge.initialize(api_key)
