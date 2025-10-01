"""
Gemini Live API Client for Real-time Bidirectional Streaming
Based on Context7 Cookbook pattern for continuous conversation
"""

import asyncio
import json
import base64
import logging
from typing import Optional, Dict, Any, Callable
from websockets.asyncio.client import connect
import time

logger = logging.getLogger(__name__)


class LiveAPIClient:
    """Manages persistent connection for continuous voice conversation using 2025 Gemini Live API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = 'models/gemini-live-2.5-flash-preview'  # Correct Gemini 2.5 Flash Live API model
        self.session = None
        self.session_active = False
        self.audio_queue = asyncio.Queue()
        self.is_playing_audio = False

    async def start_session(self,
                           audio_callback: Optional[Callable] = None,
                           text_callback: Optional[Callable] = None,
                           voice_name: str = "Aoede"):
        """Start a session using proper 2025 Gemini Live API"""

        try:
            from google import genai
            from google.genai import types

            # Create Gemini client
            client = genai.Client(api_key=self.api_key)

            # Live API configuration using Context7 best practices with TRANSCRIPT SUPPORT
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO", "TEXT"],
                system_instruction="""You are a helpful assistant having a natural conversation.
                Please speak naturally and respond conversationally.
                Keep your responses concise but complete.""",
                generation_config=types.GenerationConfig(
                    max_output_tokens=2048,
                    temperature=0.7,
                    top_p=0.95,
                ),
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name  # Configurable voice per agent
                        )
                    )
                ),
                # CRITICAL: Enable transcript support for both input and output (SIMPLE CONFIG)
                input_audio_transcription=types.AudioTranscriptionConfig(),  # Transcribe user speech
                output_audio_transcription=types.AudioTranscriptionConfig()  # Transcribe AI speech
            )

            # Connect using proper 2025 Live API
            self.session = client.aio.live.connect(model=self.model, config=config)
            self.session_active = True
            logger.info(f"Connected to 2025 Gemini Live API with model: {self.model}")

            # Start the session (using context manager)
            async with self.session as live_session:

                # Task 1: Continuously send audio from queue using 2025 API
                async def send_audio_stream():
                    """Send audio using proper 2025 Live API format"""
                    while self.session_active:
                        try:
                            audio_data = await asyncio.wait_for(
                                self.audio_queue.get(),
                                timeout=0.1
                            )

                            if audio_data and len(audio_data) > 0:
                                # Convert base64 audio to bytes if needed
                                if isinstance(audio_data, str):
                                    try:
                                        audio_bytes = base64.b64decode(audio_data)
                                    except:
                                        logger.error(f"Failed to decode base64 audio")
                                        continue
                                else:
                                    audio_bytes = audio_data

                                # Use 2025 format: send_realtime_input with Blob
                                audio_blob = types.Blob(
                                    data=audio_bytes,
                                    mime_type="audio/pcm;rate=16000"  # Input at 16kHz as per docs
                                )

                                await live_session.send_realtime_input(audio=audio_blob)
                                logger.info(f"Sent audio chunk: {len(audio_bytes)} bytes to Live API")

                        except asyncio.TimeoutError:
                            continue
                        except Exception as e:
                            logger.error(f"Error sending audio: {e}")
                            break

                # Task 2: Receive responses using 2025 API
                async def receive_responses():
                    """Receive responses from 2025 Live API"""
                    logger.info("Starting to listen for Live API responses...")
                    try:
                        async for response in live_session.receive():
                            logger.info(f"Received response from Live API: {type(response)} - {response}")

                            # Handle server content with model turn (most common pattern)
                            if hasattr(response, 'server_content') and response.server_content:
                                server_content = response.server_content
                                logger.info(f"Processing server_content: {type(server_content)}")

                                # CRITICAL: Handle transcript messages FIRST
                                if hasattr(server_content, 'input_transcription') and server_content.input_transcription:
                                    transcript_text = server_content.input_transcription.text
                                    if transcript_text:  # Only process non-empty transcripts
                                        logger.info(f"User transcript: {transcript_text}")
                                        if text_callback:
                                            # Send user transcript with special marker
                                            await text_callback({
                                                'type': 'transcript',
                                                'text': f"[USER]: {transcript_text}"
                                            })

                                if hasattr(server_content, 'output_transcription') and server_content.output_transcription:
                                    transcript_text = server_content.output_transcription.text
                                    if transcript_text:  # Only process non-empty transcripts
                                        logger.info(f"AI transcript: {transcript_text}")
                                        if text_callback:
                                            # Send AI transcript
                                            await text_callback({
                                                'type': 'transcript',
                                                'text': transcript_text
                                            })

                                # Handle interruption first - this is critical for natural conversation
                                if hasattr(server_content, 'interrupted') and server_content.interrupted:
                                    logger.info("Interruption detected! Stopping current audio playback")
                                    self.is_playing_audio = False
                                    # Clear audio queue when interrupted
                                    while not self.audio_queue.empty():
                                        try:
                                            self.audio_queue.get_nowait()
                                        except asyncio.QueueEmpty:
                                            break
                                    continue

                                # Handle model turn responses
                                if hasattr(server_content, 'model_turn') and server_content.model_turn:
                                    model_turn = server_content.model_turn
                                    logger.info(f"Processing model_turn with {len(model_turn.parts)} parts")

                                    for part in model_turn.parts:
                                        # Audio response
                                        if hasattr(part, 'inline_data') and part.inline_data:
                                            audio_data = part.inline_data.data
                                            if audio_callback and audio_data and self.session_active:
                                                logger.info(f"Sending audio response: {len(audio_data)} bytes")
                                                await audio_callback(audio_data)

                                        # Text response
                                        if hasattr(part, 'text') and part.text:
                                            if text_callback:
                                                logger.info(f"Sending text response: {part.text}")
                                                await text_callback({
                                                    'type': 'transcript',
                                                    'text': part.text
                                                })

                                # Handle turn complete signals
                                if hasattr(server_content, 'turn_complete') and server_content.turn_complete:
                                    logger.info("Turn complete signal received - ready for next user input")

                            # Handle direct responses (alternative API structure)
                            elif hasattr(response, 'candidates') and response.candidates:
                                logger.info(f"Processing candidates response: {len(response.candidates)} candidates")
                                for candidate in response.candidates:
                                    if hasattr(candidate, 'content') and candidate.content:
                                        for part in candidate.content.parts:
                                            if hasattr(part, 'inline_data') and part.inline_data:
                                                if audio_callback:
                                                    await audio_callback(part.inline_data.data)
                                            if hasattr(part, 'text') and part.text:
                                                if text_callback:
                                                    await text_callback({
                                                        'type': 'transcript',
                                                        'text': part.text
                                                    })

                            # Handle setup complete or other status messages
                            elif hasattr(response, 'setup_complete'):
                                logger.info("Live API setup complete")

                            else:
                                logger.info(f"Unknown response format: {dir(response)}")

                    except Exception as e:
                        logger.error(f"Error in receive_responses: {e}", exc_info=True)

                # Start both tasks
                tasks = [
                    asyncio.create_task(send_audio_stream()),
                    asyncio.create_task(receive_responses())
                ]

                # Wait for tasks
                await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"Live API session error: {e}")
            self.session_active = False

    async def send_text(self, text: str):
        """Send text input to the conversation"""
        if not self.session or not self.session_active:
            logger.error("No active session")
            return

        # Use the 2025 Live API session to send text
        try:
            from google.genai import types
            # Send text input using the 2025 Live API format
            await self.session.send_realtime_input(text=text)
            logger.info(f"Sent text: {text}")
        except Exception as e:
            logger.error(f"Failed to send text: {e}")

    async def send_audio_chunk(self, audio_data: bytes):
        """Queue audio data for streaming to 2025 Live API"""
        if self.session_active:
            await self.audio_queue.put(audio_data)

    async def end_session(self):
        """End the 2025 Live API session"""
        self.session_active = False
        if self.session:
            self.session = None
            logger.info("2025 Live API session ended")


class ContinuousVoiceSession:
    """Manages a continuous voice conversation session"""

    def __init__(self, api_key: str):
        self.client = LiveAPIClient(api_key)
        self.audio_buffer = []
        self.is_speaking = False

    async def start(self, websocket_callback, voice_name="Aoede"):
        """Start continuous conversation session"""

        async def handle_audio(audio_bytes):
            """Handle incoming audio from Live API"""
            # Send to frontend via WebSocket
            await websocket_callback({
                'type': 'audio_chunk',
                'audio': base64.b64encode(audio_bytes).decode('utf-8')
            })

        async def handle_text(text):
            """Handle incoming text from Live API"""
            # Send transcript to frontend
            await websocket_callback({
                'type': 'transcript',
                'text': text
            })

        # Start the Live API session with callbacks
        asyncio.create_task(
            self.client.start_session(
                audio_callback=handle_audio,
                text_callback=handle_text,
                voice_name=voice_name
            )
        )

        # Give it a moment to connect
        await asyncio.sleep(0.5)

        logger.info("Continuous voice session started")

    async def process_audio(self, audio_data: bytes):
        """Process incoming audio from user"""
        # Send directly to Live API queue
        await self.client.send_audio_chunk(audio_data)

    async def process_text(self, text: str):
        """Process text input from user"""
        await self.client.send_text(text)

    async def stop(self):
        """Stop the continuous session"""
        await self.client.end_session()