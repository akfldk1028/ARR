"""
A2A Handler - Agent-to-Agent 통신 및 처리
워커 에이전트 간 통신, 의미적 라우팅, TTS 변환 처리
"""

import asyncio
import base64
import json
import logging
import re
from typing import Dict, Any, Optional
from uuid import uuid4

logger = logging.getLogger('gemini.consumers')

class A2AHandler:
    """A2A (Agent-to-Agent) 관련 처리를 담당하는 핸들러"""

    def __init__(self, consumer):
        self.consumer = consumer
        self.websocket_send = consumer.send
        self.session_id = consumer.session_id
        self.user_obj = consumer.user_obj
        self.worker_manager = consumer.worker_manager
        self.gemini_service = consumer.gemini_service
        self.current_agent_slug = consumer.current_agent_slug

    async def handle_text(self, data):
        """Handle text messages with A2A integration"""
        content = data.get('message', '').strip()
        if not content or len(content) > 10000:
            await self.consumer._send_error("Invalid message content")
            return

        try:
            # Save user message
            user_message = await self.consumer._save_message(content, 'text', 'user')

            # Process with A2A
            result = await self._process_with_a2a(content)

            if result['success']:
                # Save and send A2A response
                await self.consumer._save_message(result['response'], 'text', 'assistant', {
                    'agent_slug': self.consumer.current_agent_slug,
                    'processing_type': 'a2a_agent'
                })

                await self.websocket_send(text_data=json.dumps({
                    'type': 'response',
                    'message': result['response'],
                    'user_message_id': str(user_message.id),
                    'agent_slug': self.consumer.current_agent_slug,
                    'success': True
                }))
            else:
                # Fallback to Gemini
                await self._fallback_to_gemini(content, user_message)

        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            await self.consumer._send_error(f"Text processing failed: {str(e)}")

    async def handle_text_audio(self, data):
        """Handle text with audio response"""
        content = data.get('message', '').strip()
        voice_name = data.get('voice', 'Aoede')

        if not content:
            await self.consumer._send_error("Empty message content")
            return

        try:
            user_message = await self.consumer._save_message(content, 'text', 'user')

            # For debugging, skip A2A and go directly to Gemini
            logger.info(f"Processing text_audio with Gemini: {content}")
            await self._process_with_gemini_tts(content, voice_name, user_message)

        except Exception as e:
            logger.error(f"Text audio processing failed: {e}")
            await self.consumer._send_error(f"Text audio processing failed: {str(e)}")

    async def handle_audio(self, data):
        """Handle audio input with transcript and A2A processing"""
        audio_data = data.get('audio', '')
        voice_name = data.get('voice', 'Aoede')

        if not audio_data:
            await self.consumer._send_error("No audio data provided")
            return

        try:
            # Decode and validate audio
            audio_bytes = base64.b64decode(audio_data)
            if len(audio_bytes) > 50 * 1024 * 1024:
                await self.consumer._send_error("Audio too large (max 50MB)")
                return

            user_message = await self.consumer._save_message("[Audio Input] Voice message", 'audio', 'user')

            # Process with Gemini to get transcript
            gemini_result = await self.gemini_service.process_audio_with_audio(
                audio_bytes, voice_name, self.session_id
            )

            user_transcript = gemini_result.get('input_transcript', '')

            if user_transcript:
                # Try A2A processing with transcript
                a2a_result = await self._process_with_a2a(user_transcript)

                if a2a_result['success']:
                    # Generate TTS for A2A response
                    await self._send_a2a_audio_response(
                        a2a_result, user_transcript, voice_name, user_message
                    )
                    return

            # Fallback to original Gemini response
            await self._send_gemini_audio_response(gemini_result, voice_name, user_message)

        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            await self.consumer._send_error(f"Audio processing failed: {str(e)}")

    async def handle_a2a_delegation(self, data):
        """Handle A2A delegation requests"""
        try:
            target_agent = data.get('target_agent')
            user_message = data.get('user_message', '')
            delegation_reason = data.get('reason', 'Semantic routing delegation')

            if not target_agent:
                await self.consumer._send_error("Target agent is required for delegation")
                return

            if not user_message:
                await self.consumer._send_error("User message is required for delegation")
                return

            # Verify target agent exists
            agent = await self.worker_manager.get_worker(target_agent)
            if not agent:
                await self.consumer._send_error(f"Target agent '{target_agent}' not found")
                return

            # Switch to target agent
            old_agent = self.consumer.current_agent_slug
            self.consumer.current_agent_slug = target_agent

            from .utils import safe_log_text
            logger.info(f"A2A delegation: {old_agent} -> {target_agent} for message: {safe_log_text(user_message[:50])}...")

            # Process message with new agent
            result = await self._process_with_a2a(user_message)

            if result['success']:
                # Save delegation message
                await self.consumer._save_message(user_message, 'text', 'user')
                await self.consumer._save_message(result['response'], 'text', 'assistant', {
                    'agent_slug': self.consumer.current_agent_slug,
                    'delegated_from': old_agent,
                    'delegation_reason': delegation_reason
                })

                # Get voice for target agent (Flight Agent = 'Kore')
                voice_name = data.get('voice', 'Kore' if target_agent == 'flight-specialist' else 'Aoede')

                # Convert Flight Agent response to TTS using existing Gemini service
                try:
                    audio_result = await self.gemini_service.process_text_with_audio_streaming(
                        result['response'], voice_name, self.session_id, callback=None
                    )

                    audio_base64 = None
                    if audio_result.get('audio') and audio_result['success']:
                        audio_base64 = base64.b64encode(audio_result['audio']).decode('utf-8')

                    # Send A2A response with audio (use existing a2a_response type)
                    await self.websocket_send(text_data=json.dumps({
                        'type': 'a2a_response',  # Use existing a2a_response type
                        'agent': agent.agent_name,
                        'message': result['response'],
                        'audio': audio_base64,
                        'voice': voice_name,
                        'agent_slug': target_agent,
                        'original_message': user_message,
                        'delegated_from': old_agent,
                        'reason': delegation_reason,
                        'success': True
                    }))

                except Exception as tts_error:
                    logger.error(f"TTS conversion failed for A2A response: {tts_error}")
                    # Fallback to text-only response
                    await self.websocket_send(text_data=json.dumps({
                        'type': 'a2a_response',
                        'agent': agent.agent_name,
                        'message': result['response'],
                        'audio': None,
                        'voice': voice_name,
                        'agent_slug': target_agent,
                        'original_message': user_message,
                        'delegated_from': old_agent,
                        'reason': delegation_reason,
                        'success': True
                    }))
            else:
                # Delegation failed, revert to original agent
                self.consumer.current_agent_slug = old_agent
                await self.consumer._send_error(f"Delegation to {target_agent} failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"A2A delegation failed: {e}")
            await self.consumer._send_error(f"A2A delegation failed: {str(e)}")

    async def handle_semantic_routing(self, data):
        """Handle LLM-based semantic routing for A2A delegation"""
        try:
            user_message = data.get('user_message', '').strip()
            current_agent = data.get('current_agent', self.consumer.current_agent_slug)

            if not user_message:
                await self.consumer._send_error("No user message provided for semantic routing")
                return

            from .utils import safe_log_text
            logger.info(f"LLM semantic routing analysis for: '{safe_log_text(user_message)}' with current agent: {current_agent}")

            # Use Gemini LLM for semantic intent analysis
            routing_result = await self._analyze_intent_with_similarity(user_message, current_agent)

            # Send semantic routing result
            await self.websocket_send(text_data=json.dumps({
                'type': 'semantic_routing_result',
                'should_delegate': routing_result['should_delegate'],
                'target_agent': routing_result['target_agent'],
                'confidence': routing_result['confidence'],
                'original_message': user_message,
                'current_agent': current_agent,
                'analysis': routing_result['analysis'],
                'reasoning': routing_result['reasoning'],
                'success': True
            }))

        except Exception as e:
            logger.error(f"Semantic routing failed: {e}")
            await self.consumer._send_error(f"Semantic routing failed: {str(e)}")

    async def _process_with_a2a(self, user_input: str) -> Dict[str, Any]:
        """Core A2A processing logic"""
        try:
            agent = await self.worker_manager.get_worker(self.consumer.current_agent_slug)
            if not agent:
                return {'success': False, 'error': 'Agent not available'}

            response = await agent.process_request(
                user_input=user_input,
                context_id=self.session_id,
                session_id=self.session_id,
                user_name=self.user_obj.username if self.user_obj else "user"
            )

            return {
                'success': True,
                'response': response,
                'agent_name': agent.agent_name
            }

        except Exception as e:
            logger.error(f"A2A processing failed: {e}")
            return {'success': False, 'error': str(e)}

    async def _process_a2a_response(self, a2a_response: str, voice_name: str, user_text: str):
        """A2A 응답을 TTS로 변환하여 전송"""
        try:
            # A2A 응답을 음성으로 변환
            audio_result = await self.gemini_service.process_text_with_audio_streaming(
                a2a_response, voice_name, self.session_id, callback=None
            )

            # 메시지 저장
            await self.consumer._save_message(user_text, 'text', 'user', {
                'delegated_to_a2a': True,
                'target_agent': voice_name
            })

            await self.consumer._save_message(
                audio_result.get('transcript', a2a_response), 'audio', 'assistant', {
                    'voice': voice_name,
                    'has_audio': audio_result['success'],
                    'from_a2a': True,
                    'input_transcript': user_text
                }
            )

            # 오디오 응답 전송
            audio_base64 = None
            if audio_result.get('audio') and audio_result['success']:
                audio_base64 = base64.b64encode(audio_result['audio']).decode('utf-8')

            await self.websocket_send(text_data=json.dumps({
                'type': 'a2a_audio_response',
                'transcript': a2a_response,
                'audio': audio_base64,
                'voice': voice_name,
                'input_transcript': user_text,
                'success': audio_result['success'],
                'source': 'a2a_agent'
            }))

            logger.info(f"A2A 응답 전송 완료: {voice_name} - {a2a_response[:50]}...")

            # Context7 패턴: interrupt 후 별도 resume 불필요
            logger.info("A2A response completed - Context7 interrupt pattern applied")

        except Exception as e:
            logger.error(f"A2A 응답 처리 실패: {e}")
            # Context7 패턴: interrupt 후 별도 resume 불필요
            await self.consumer._send_error(f"A2A 응답 처리 실패: {str(e)}")

    # Context7 패턴: TTS 재생 후 별도 resume 불필요 (메서드 제거)

    async def _analyze_intent_with_similarity(self, user_message: str, current_agent: str) -> dict:
        """Use semantic similarity to analyze user intent and determine routing"""
        try:
            # Import sentence transformers
            from sentence_transformers import SentenceTransformer, util
            import asyncio
            import concurrent.futures

            # Agent capability descriptions for similarity comparison
            agent_capabilities = {
                'flight-specialist': [
                    "항공편 검색 및 예약",
                    "비행기표 구매 및 변경",
                    "비행기 예약해줘",
                    "비행기 예약",
                    "항공편 예약",
                    "항공료 비교 및 조회",
                    "좌석 선택 및 업그레이드",
                    "수하물 정보 및 규정",
                    "항공편 취소 및 환불",
                    "공항 정보 및 체크인",
                    "비행 스케줄",
                    "항공사 정보",
                    "항공권 예약",
                    "항공권 구매",
                    "비행기 티켓"
                ],
                'hotel-specialist': [
                    "호텔 검색 및 예약",
                    "숙박 시설 조회 및 비교",
                    "체크인 체크아웃 정보",
                    "객실 서비스 및 어메니티",
                    "호텔 리뷰 및 평점",
                    "숙박 요금 및 할인",
                    "호텔 취소 및 변경",
                    "호텔 예약해줘",
                    "숙박 예약",
                    "호텔 찾기"
                ]
            }

            # Load model (use a lightweight Korean-supported model)
            def load_model_and_compute():
                model = SentenceTransformer("distiluse-base-multilingual-cased")

                # Encode user message
                user_embedding = model.encode([user_message])

                # Compute similarities for each agent
                similarities = {}
                for agent, capabilities in agent_capabilities.items():
                    # Encode capabilities
                    capability_embeddings = model.encode(capabilities)

                    # Compute similarity between user message and each capability
                    sims = util.cos_sim(user_embedding, capability_embeddings)

                    # Take the maximum similarity across all capabilities
                    max_sim = float(sims.max())
                    similarities[agent] = max_sim

                return similarities

            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                similarities = await loop.run_in_executor(executor, load_model_and_compute)

            # Determine best agent based on similarity
            best_agent = max(similarities, key=similarities.get)
            best_score = similarities[best_agent]

            # Set threshold for delegation (임계값: 0.6)
            threshold = 0.6
            should_delegate = best_score >= threshold

            from .utils import safe_log_text
            logger.info(f"Semantic similarity analysis: {safe_log_text(user_message)} | "
                       f"flight: {similarities.get('flight-specialist', 0):.3f} | "
                       f"hotel: {similarities.get('hotel-specialist', 0):.3f} | "
                       f"best: {best_agent}({best_score:.3f}) | delegate: {should_delegate}")

            # Additional validation
            if should_delegate and best_agent == current_agent:
                should_delegate = False

            return {
                'should_delegate': should_delegate,
                'target_agent': best_agent if should_delegate else None,
                'confidence': best_score,
                'analysis': f"Semantic similarity: {best_agent}({best_score:.3f})",
                'reasoning': f"최고 유사도: {best_score:.3f} (임계값: {threshold})"
            }

        except Exception as e:
            logger.error(f"Semantic similarity analysis failed: {e}")
            return {
                'should_delegate': False,
                'target_agent': None,
                'confidence': 0.0,
                'analysis': "유사도 분석 실패, Live API 처리",
                'reasoning': f"분석 중 오류 발생: {str(e)}"
            }

    # Helper methods for Gemini processing
    async def _process_with_gemini_tts(self, content: str, voice_name: str, user_message):
        """Process text with Gemini TTS"""
        try:
            result = await self.gemini_service.process_text_with_audio_streaming(
                content, voice_name, self.session_id, callback=None
            )

            await self.consumer._save_message(result.get('transcript', content), 'audio', 'assistant', {
                'voice': voice_name,
                'has_audio': result['success']
            })

            audio_base64 = None
            if result.get('audio') and result['success']:
                audio_base64 = base64.b64encode(result['audio']).decode('utf-8')

            await self.websocket_send(text_data=json.dumps({
                'type': 'audio_response',
                'transcript': result.get('transcript', ''),
                'audio': audio_base64,
                'voice': voice_name,
                'user_message_id': str(user_message.id),
                'success': result['success']
            }))

        except Exception as e:
            logger.error(f"Gemini TTS processing failed: {e}")
            await self.consumer._send_error(f"TTS processing failed: {str(e)}")

    async def _fallback_to_gemini(self, content: str, user_message):
        """Fallback to Gemini when A2A fails"""
        try:
            result = await self.gemini_service.process_text_with_streaming(
                content, self.session_id, callback=None
            )

            await self.consumer._save_message(result['text'], 'text', 'assistant', {
                'model': result['model'],
                'fallback_from_a2a': True
            })

            await self.websocket_send(text_data=json.dumps({
                'type': 'response',
                'message': result['text'],
                'user_message_id': str(user_message.id),
                'model': result['model'],
                'success': True
            }))

        except Exception as e:
            logger.error(f"Gemini fallback failed: {e}")
            await self.consumer._send_error(f"Processing failed: {str(e)}")

    async def _send_a2a_audio_response(self, a2a_result, user_transcript, voice_name, user_message):
        """Send A2A response with TTS"""
        try:
            # Generate TTS for A2A response
            audio_result = await self.gemini_service.process_text_with_audio_streaming(
                a2a_result['response'], voice_name, self.session_id, callback=None
            )

            audio_base64 = None
            if audio_result.get('audio') and audio_result['success']:
                audio_base64 = base64.b64encode(audio_result['audio']).decode('utf-8')

            await self.consumer._save_message(a2a_result['response'], 'audio', 'assistant', {
                'agent_slug': self.consumer.current_agent_slug,
                'voice': voice_name,
                'has_audio': audio_result['success'],
                'input_transcript': user_transcript
            })

            await self.websocket_send(text_data=json.dumps({
                'type': 'audio_response',
                'transcript': a2a_result['response'],
                'input_transcript': user_transcript,
                'audio': audio_base64,
                'voice': voice_name,
                'user_message_id': str(user_message.id),
                'agent_slug': self.consumer.current_agent_slug,
                'success': audio_result['success']
            }))

        except Exception as e:
            logger.error(f"A2A TTS failed: {e}")
            await self.consumer._send_error(f"A2A TTS failed: {str(e)}")

    async def _send_gemini_audio_response(self, gemini_result, voice_name, user_message):
        """Send Gemini audio response"""
        try:
            await self.consumer._save_message(
                gemini_result.get('transcript', 'No transcript available'),
                'audio', 'assistant', {
                    'voice': voice_name,
                    'has_audio': gemini_result['success'],
                    'input_transcript': gemini_result.get('input_transcript', '')
                }
            )

            audio_base64 = None
            if gemini_result.get('audio') and gemini_result['success']:
                audio_base64 = base64.b64encode(gemini_result['audio']).decode('utf-8')

            await self.websocket_send(text_data=json.dumps({
                'type': 'audio_response',
                'transcript': gemini_result.get('transcript', ''),
                'input_transcript': gemini_result.get('input_transcript', ''),
                'audio': audio_base64,
                'voice': voice_name,
                'user_message_id': str(user_message.id),
                'success': gemini_result['success']
            }))

        except Exception as e:
            logger.error(f"Gemini audio response failed: {e}")
            await self.consumer._send_error(f"Gemini audio response failed: {str(e)}")