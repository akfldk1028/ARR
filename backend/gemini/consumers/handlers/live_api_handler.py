"""
Live API Handler - Gemini Live API 관련 처리
실시간 음성 세션 시작/종료 및 음성 처리
"""

import asyncio
import base64
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger('gemini.consumers')

class LiveAPIHandler:
    """Live API 관련 처리를 담당하는 핸들러"""

    def __init__(self, consumer):
        self.consumer = consumer
        self.websocket_send = consumer.send
        self.session_id = consumer.browser_session_id
        self.user_obj = consumer.user_obj
        self.worker_manager = consumer.worker_manager

    async def handle_start_voice_session(self, data):
        """Start Context7 Live API session with A2A bridge"""
        try:
            from config.api_config import APIConfig

            api_key = APIConfig.get_api_key('google')
            if not api_key:
                await self._send_voice_status('error', 'API key not configured')
                return

            # Get Context7 Live API client
            from ..services.websocket_live_client import ContinuousVoiceSession
            self.consumer.voice_session = ContinuousVoiceSession(api_key)

            # WebSocket callback to send messages to frontend
            async def websocket_callback(message):
                """Handle Live API messages with smart routing"""
                try:
                    message_type = message.get('type')
                    sender = message.get('sender')
                    source = message.get('source')

                    if message_type == 'transcript':
                        if sender == 'user' and source == 'live_api_input':
                            # 사용자 입력에 대해 semantic routing 적용
                            user_text = message.get('text', '')
                            from ..utils import safe_log_text
                            logger.info(f"사용자 입력 transcript: {safe_log_text(user_text)}")

                            # Context7 패턴: Live API는 계속 진행, A2A 라우팅은 병렬 처리
                            logger.info("Live API 계속 진행, A2A 라우팅 병렬 처리 시작")

                            # 백그라운드에서 A2A 라우팅 처리 (Context7 패턴)
                            async def parallel_a2a_routing():
                                try:
                                    routing_result = await self.consumer.a2a_handler._analyze_intent_with_similarity(user_text, 'live-api')

                                    should_delegate = routing_result.get('should_delegate', False)
                                    confidence = routing_result.get('confidence', 0.0)
                                    target_agent = routing_result.get('target_agent')

                                    logger.info(f"A2A 라우팅 결과: delegate={should_delegate}, agent={target_agent}, confidence={confidence:.3f}")

                                    if should_delegate and confidence >= 0.7:  # 높은 신뢰도에서만 interrupt
                                        logger.info(f"높은 신뢰도 A2A 라우팅: {target_agent} (신뢰도: {confidence:.3f})")

                                        # A2A 에이전트 처리
                                        agent = await self.worker_manager.get_worker(target_agent)
                                        if agent:
                                            # Context7 패턴: Live API interrupt 신호 전송
                                            if self.consumer.voice_session:
                                                await self.consumer.voice_session.send_interrupt()
                                                logger.info("Live API interrupt 신호 전송됨")

                                            # A2A 응답 생성
                                            a2a_response = await agent.process_request(
                                                user_input=user_text,
                                                context_id=self.session_id,
                                                session_id=self.session_id,
                                                user_name=self.user_obj.username if self.user_obj else "user"
                                            )

                                            # A2A 응답을 TTS로 변환하여 전송
                                            voice_name = 'Kore' if target_agent == 'flight-specialist' else 'Aoede'
                                            logger.info(f"A2A 응답 TTS 처리 시작 (음성: {voice_name})")
                                            await self.consumer.a2a_handler._process_a2a_response(a2a_response, voice_name, user_text)
                                        else:
                                            logger.warning(f"Agent {target_agent} not available")
                                    else:
                                        logger.info(f"A2A 라우팅 안함 (신뢰도: {confidence:.3f} < 0.7) - Live API 계속 진행")

                                except Exception as e:
                                    logger.error(f"A2A parallel processing failed: {e}")

                            # Context7 패턴: 비동기 태스크로 병렬 처리
                            asyncio.create_task(parallel_a2a_routing())

                        elif sender == 'ai' and source == 'live_api_output':
                            # AI 출력은 그대로 frontend로 전송
                            logger.info(f"AI 응답 transcript: {message.get('text', '')[:50]}...")

                    elif message_type == 'audio_chunk':
                        # Audio response from AI - 기존과 동일
                        if not message.get('sender'):
                            message['sender'] = 'ai'
                        if not message.get('source'):
                            message['source'] = 'live_api'

                    # 모든 메시지를 frontend로 전송
                    await self.websocket_send(text_data=json.dumps(message))

                except Exception as e:
                    logger.error(f"Websocket callback error: {e}")

            # Connect Context7 Live API session
            await self.consumer.voice_session.start(
                websocket_callback=websocket_callback,
                voice_name="Aoede"
            )

            await self._send_voice_status('started', 'Context7 Live API + A2A 브릿지 활성화!')

        except Exception as e:
            logger.error(f"Context7 Live API session start failed: {e}")
            await self._send_voice_status('error', f'연결 실패: {str(e)}')

    async def handle_stop_voice_session(self, data):
        """Stop Context7 Live API session"""
        try:
            if self.consumer.voice_session:
                await self.consumer.voice_session.stop()
                self.consumer.voice_session = None
            await self._send_voice_status('stopped', 'Context7 Live API 세션 종료')
        except Exception as e:
            logger.error(f"Context7 voice session stop failed: {e}")
            await self.consumer._send_error(f"세션 종료 실패: {str(e)}")

    async def handle_voice_audio_chunk(self, data):
        """Process voice audio chunk with Context7 Live API"""
        try:
            if not self.consumer.voice_session:
                await self.consumer._send_error('Live API 세션이 없습니다')
                return

            audio_data = data.get('audio')
            if not audio_data:
                return

            # Basic validation
            try:
                audio_bytes = base64.b64decode(audio_data)
                if len(audio_bytes) < 100 or len(audio_bytes) > 50000:
                    return  # Skip invalid chunks
            except Exception:
                return  # Skip invalid base64

            # Send to Context7 Live API
            await self.consumer.voice_session.process_audio(audio_data)

        except Exception as e:
            logger.error(f"Context7 audio processing failed: {e}")
            await self.consumer._send_error(f"음성 처리 실패: {str(e)}")

    async def _send_voice_status(self, status: str, message: str):
        """Send voice session status"""
        await self.websocket_send(text_data=json.dumps({
            'type': 'voice_session_status',
            'status': status,
            'message': message
        }))