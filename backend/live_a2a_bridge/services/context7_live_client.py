"""
Context7 Pattern Live API Client
Based on official Google GenAI SDK patterns

Live API → A2A → TTS Bridge Implementation
"""

import asyncio
import base64
import json
import logging
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger(__name__)


class Context7LiveClient:
    """
    Live API client following Context7 documentation patterns

    Key Flow:
    1. User speaks → Live API recognizes transcript
    2. Transcript → A2A Worker processing
    3. A2A Response → Live API TTS synthesis
    4. TTS Audio → User hears response
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = None
        self.session_active = False
        self.websocket_callback = None
        self.a2a_processor = None

    async def connect_live_session(self, websocket_callback: Callable, a2a_processor: Callable):
        """
        Connect to Live API using Context7 patterns

        Args:
            websocket_callback: Send messages to frontend
            a2a_processor: Process transcript through A2A system
        """
        try:
            from google import genai
            from google.genai import types

            # Store callbacks
            self.websocket_callback = websocket_callback
            self.a2a_processor = a2a_processor

            # Initialize client
            client = genai.Client(api_key=self.api_key)

            # Context7 Pattern: Live Connection Config
            config = types.LiveConnectConfig(
                # Audio-only response for clean integration
                responseModalities=[types.Modality.AUDIO],

                # 🎯 KEY: Enable transcript support (Critical for A2A bridge)
                inputAudioTranscription=types.AudioTranscriptionConfig(),
                outputAudioTranscription=types.AudioTranscriptionConfig(),

                # System instruction
                systemInstruction=types.Content(parts=[
                    types.Part(text="""
                    당신은 한국어 AI 어시스턴트입니다.
                    사용자가 한국어로 말하면 자연스럽게 한국어로 응답해주세요.
                    필요시 전문가 에이전트에게 작업을 위임할 수 있습니다.
                    """)
                ]),

                # Generation config
                generationConfig=types.GenerationConfig(
                    temperature=0.7,
                    maxOutputTokens=1024,
                ),

                # Speech config
                speechConfig=types.SpeechConfig(
                    voiceConfig=types.VoiceConfig(
                        prebuiltVoiceConfig=types.PrebuiltVoiceConfig(
                            voiceName="Aoede"
                        )
                    )
                )
            )

            # Context7 Pattern: Connection with callbacks
            callbacks = types.LiveCallbacks(
                onopen=self._on_open,
                onmessage=self._on_message,
                onerror=self._on_error,
                onclose=self._on_close
            )

            # Connect
            self.session = await client.aio.live.connect(
                model="models/gemini-live-2.5-flash-preview",
                config=config,
                callbacks=callbacks
            )

            self.session_active = True
            logger.info("Context7 Live API connected successfully")

            # Notify frontend
            await self._send_status("connected", "Live API connected - 말씀하세요!")

        except Exception as e:
            logger.error(f"Live API connection failed: {e}")
            await self._send_status("error", f"연결 실패: {str(e)}")
            raise

    async def _on_open(self):
        """Connection opened"""
        logger.info("Live API connection opened")
        await self._send_status("ready", "음성 인식 준비완료!")

    async def _on_message(self, message):
        """
        🔥 CORE: Message handler - Live API → A2A → TTS bridge

        This is where the magic happens!
        """
        try:
            logger.debug(f"Live API message: {type(message)}")

            # Handle server content
            if hasattr(message, 'serverContent') and message.serverContent:
                server_content = message.serverContent

                # 🎯 Input transcript → A2A bridge
                if (hasattr(server_content, 'inputTranscription') and
                    server_content.inputTranscription and
                    server_content.inputTranscription.text):

                    user_text = server_content.inputTranscription.text.strip()
                    if user_text:
                        logger.info(f"👤 User: {user_text}")

                        # Send to frontend
                        await self._send_message('user_transcript', {
                            'text': user_text,
                            'source': 'live_api'
                        })

                        # 🔥 Process through A2A system
                        await self._process_through_a2a(user_text)

                # Output transcript (AI speaking)
                if (hasattr(server_content, 'outputTranscription') and
                    server_content.outputTranscription and
                    server_content.outputTranscription.text):

                    ai_text = server_content.outputTranscription.text.strip()
                    if ai_text:
                        logger.info(f"🤖 AI: {ai_text}")

                        await self._send_message('ai_transcript', {
                            'text': ai_text,
                            'source': 'live_api'
                        })

                # Model turn (audio response)
                if hasattr(server_content, 'modelTurn') and server_content.modelTurn:
                    await self._handle_model_turn(server_content.modelTurn)

                # Turn complete
                if hasattr(server_content, 'turnComplete') and server_content.turnComplete:
                    logger.info("턴 완료 - 다음 입력 대기")
                    await self._send_message('turn_complete', {'ready': True})

            # Setup complete
            elif hasattr(message, 'setupComplete'):
                logger.info("Live API setup complete")
                await self._send_message('setup_complete', {'ready': True})

        except Exception as e:
            logger.error(f"Message processing error: {e}")
            await self._send_message('error', {'message': str(e)})

    async def _process_through_a2a(self, user_text: str):
        """
        🎯 CORE: Process user transcript through A2A system

        This bridges Live API to A2A workers
        """
        try:
            logger.info(f"A2A 처리 시작: {user_text}")

            # Process through A2A
            if self.a2a_processor:
                a2a_result = await self.a2a_processor(user_text)

                if a2a_result and a2a_result.get('success'):
                    response_text = a2a_result['response']
                    agent_info = a2a_result.get('agent_name', 'AI')

                    logger.info(f"✅ A2A 성공: {response_text[:50]}...")

                    # Send A2A response to frontend
                    await self._send_message('a2a_response', {
                        'text': response_text,
                        'agent': agent_info,
                        'source': 'a2a_worker'
                    })

                    # 🔥 KEY: Send back to Live API for TTS
                    await self._send_response_to_live_api(response_text)

                else:
                    error_msg = a2a_result.get('error', 'A2A 처리 실패')
                    logger.warning(f"❌ A2A 실패: {error_msg}")

                    await self._send_message('a2a_error', {
                        'error': error_msg
                    })

        except Exception as e:
            logger.error(f"A2A processing error: {e}")
            await self._send_message('error', {'message': f'A2A 오류: {str(e)}'})

    async def _send_response_to_live_api(self, response_text: str):
        """
        🔥 KEY: Send A2A response back to Live API for TTS

        This completes the bridge: Live API → A2A → Live API TTS
        """
        try:
            if not self.session or not self.session_active:
                logger.error("Live API session not active")
                return

            logger.info(f"Live API TTS 생성 중: {response_text[:30]}...")

            # Context7 Pattern: Send client content for TTS
            from google.genai import types

            # Send as user message to trigger AI response with TTS
            await self.session.sendClientContent(
                turns=[
                    types.Content(
                        role=types.Role.USER,
                        parts=[types.Part(text=response_text)]
                    )
                ],
                turnComplete=True
            )

            logger.info("A2A 응답을 Live API TTS로 전송 완료")

        except Exception as e:
            logger.error(f"Live API TTS 전송 실패: {e}")

    async def _handle_model_turn(self, model_turn):
        """Handle model turn with audio/text response"""
        try:
            logger.info(f"Model turn: {len(model_turn.parts)} parts")

            for part in model_turn.parts:
                # Audio response
                if hasattr(part, 'inlineData') and part.inlineData:
                    audio_data = part.inlineData.data
                    if audio_data:
                        # Convert to base64 for WebSocket
                        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

                        await self._send_message('audio_chunk', {
                            'audio': audio_base64,
                            'source': 'live_api_tts'
                        })

                        logger.info(f"Audio chunk: {len(audio_data)} bytes")

                # Text response
                if hasattr(part, 'text') and part.text:
                    logger.info(f"Text response: {part.text}")

                    await self._send_message('text_response', {
                        'text': part.text,
                        'source': 'live_api'
                    })

        except Exception as e:
            logger.error(f"Model turn handling error: {e}")

    async def _on_error(self, error):
        """Handle connection errors"""
        logger.error(f"Live API error: {error}")
        await self._send_status("error", f"오류 발생: {str(error)}")

    async def _on_close(self, event):
        """Handle connection close"""
        logger.info("Live API connection closed")
        self.session_active = False
        await self._send_status("disconnected", "연결 종료")

    async def send_audio(self, audio_data: str):
        """
        Send audio input to Live API

        Args:
            audio_data: Base64 encoded audio
        """
        try:
            if not self.session or not self.session_active:
                logger.error("Live API session not available")
                return

            # Decode audio
            audio_bytes = base64.b64decode(audio_data)

            # Create blob
            from google.genai import types

            audio_blob = types.Blob(
                mimeType="audio/pcm;rate=16000",
                data=audio_bytes
            )

            # Send realtime input
            await self.session.sendRealtimeInput(audio=audio_blob)

            logger.debug(f"Audio sent: {len(audio_bytes)} bytes")

        except Exception as e:
            logger.error(f"Audio send error: {e}")

    async def close_session(self):
        """Close Live API session"""
        try:
            self.session_active = False

            if self.session:
                await self.session.close()
                self.session = None

            logger.info("Live API session closed")
            await self._send_status("closed", "세션 종료")

        except Exception as e:
            logger.error(f"Session close error: {e}")

    # Helper methods
    async def _send_status(self, status: str, message: str):
        """Send status update to frontend"""
        if self.websocket_callback:
            await self.websocket_callback({
                'type': 'live_api_status',
                'status': status,
                'message': message
            })

    async def _send_message(self, msg_type: str, data: Dict[str, Any]):
        """Send message to frontend"""
        if self.websocket_callback:
            await self.websocket_callback({
                'type': msg_type,
                **data
            })


# Singleton management
_live_client: Optional[Context7LiveClient] = None


def get_live_client(api_key: str) -> Context7LiveClient:
    """Get or create Live API client instance"""
    global _live_client
    if _live_client is None:
        _live_client = Context7LiveClient(api_key)
    return _live_client