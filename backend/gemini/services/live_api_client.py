"""
Gemini Live API Client for Real-time Bidirectional Streaming

Uses the official google-genai SDK (2026) with:
- client.aio.live.connect() for session management
- send_realtime_input(audio=Blob) for audio streaming
- send_client_content() for text input
- send_tool_response() for function calling
- audio_stream_end signal for stream lifecycle
- activity_start/end for user activity tracking
"""

import asyncio
import base64
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class LiveAPIClient:
    """Manages persistent connection for continuous voice conversation
    using the 2026 Gemini Live API (google-genai SDK)."""

    def __init__(self, api_key: str, model: str = "gemini-live-2.5-flash-preview"):
        self.api_key = api_key
        self.model = model
        self._live_session = None
        self.session_active = False
        self.audio_queue = asyncio.Queue()
        self.is_playing_audio = False
        self._tools = []
        self._tool_handlers = {}

    def register_tool(self, name: str, description: str, handler: Callable,
                      parameters: Optional[dict] = None):
        """Register a function calling tool for the Live API session.

        Args:
            name: Tool function name.
            description: Description for the LLM.
            handler: Async callable that takes parameters and returns a dict result.
            parameters: JSON Schema for parameters (optional).
        """
        decl = {"name": name, "description": description}
        if parameters:
            decl["parameters"] = parameters
        self._tools.append(decl)
        self._tool_handlers[name] = handler
        logger.info("Registered Live API tool: %s", name)

    async def start_session(
        self,
        audio_callback: Optional[Callable] = None,
        text_callback: Optional[Callable] = None,
        voice_name: str = "Aoede",
        system_instruction: str = "",
    ):
        """Start a Live API session with audio + text + function calling."""

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)

            # Build config
            config = {
                "response_modalities": ["AUDIO", "TEXT"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {"voice_name": voice_name}
                    }
                },
                "input_audio_transcription": {},
                "output_audio_transcription": {},
            }

            if system_instruction:
                config["system_instruction"] = system_instruction

            # Function calling tools
            if self._tools:
                config["tools"] = [{"function_declarations": self._tools}]

            # Connect
            async with client.aio.live.connect(
                model=self.model, config=config
            ) as live_session:
                self._live_session = live_session
                self.session_active = True
                logger.info("Connected to Gemini Live API: %s", self.model)

                async def send_audio_stream():
                    while self.session_active:
                        try:
                            audio_data = await asyncio.wait_for(
                                self.audio_queue.get(), timeout=0.1
                            )
                            if not audio_data:
                                continue

                            if isinstance(audio_data, str):
                                try:
                                    audio_bytes = base64.b64decode(audio_data)
                                except (ValueError, base64.binascii.Error):
                                    logger.error("Failed to decode base64 audio")
                                    continue
                            else:
                                audio_bytes = audio_data

                            await live_session.send_realtime_input(
                                audio=types.Blob(
                                    data=audio_bytes,
                                    mime_type="audio/pcm;rate=16000",
                                )
                            )
                        except asyncio.TimeoutError:
                            continue
                        except Exception as e:
                            logger.error("Error sending audio: %s", e)
                            break

                async def receive_responses():
                    try:
                        async for response in live_session.receive():
                            # -- server_content --
                            sc = getattr(response, "server_content", None)
                            if sc:
                                # Transcript (input)
                                it = getattr(sc, "input_transcription", None)
                                if it and it.text and text_callback:
                                    await text_callback({
                                        "type": "transcript",
                                        "text": f"[USER]: {it.text}",
                                    })

                                # Transcript (output)
                                ot = getattr(sc, "output_transcription", None)
                                if ot and ot.text and text_callback:
                                    await text_callback({
                                        "type": "transcript",
                                        "text": ot.text,
                                    })

                                # Interruption
                                if getattr(sc, "interrupted", False):
                                    logger.info("Interruption detected")
                                    self.is_playing_audio = False
                                    while not self.audio_queue.empty():
                                        try:
                                            self.audio_queue.get_nowait()
                                        except asyncio.QueueEmpty:
                                            break
                                    continue

                                # Model turn (audio + text parts)
                                mt = getattr(sc, "model_turn", None)
                                if mt:
                                    for part in mt.parts:
                                        if hasattr(part, "inline_data") and part.inline_data:
                                            if audio_callback and self.session_active:
                                                await audio_callback(part.inline_data.data)
                                        if hasattr(part, "text") and part.text:
                                            if text_callback:
                                                await text_callback({
                                                    "type": "transcript",
                                                    "text": part.text,
                                                })

                                # Turn complete
                                if getattr(sc, "turn_complete", False):
                                    logger.debug("Turn complete")

                            # -- tool_call (function calling) --
                            tc = getattr(response, "tool_call", None)
                            if tc:
                                function_responses = []
                                for fc in tc.function_calls:
                                    handler = self._tool_handlers.get(fc.name)
                                    if handler:
                                        args = dict(fc.args) if fc.args else {}
                                        logger.info("Tool call: %s(%s)", fc.name, args)
                                        try:
                                            result = await handler(**args) if args else await handler()
                                        except Exception as e:
                                            logger.error("Tool %s failed: %s", fc.name, e)
                                            result = {"error": str(e)}
                                    else:
                                        result = {"error": f"Unknown tool: {fc.name}"}

                                    function_responses.append(
                                        types.FunctionResponse(
                                            id=fc.id, name=fc.name, response=result
                                        )
                                    )

                                    if text_callback:
                                        await text_callback({
                                            "type": "tool_call",
                                            "name": fc.name,
                                            "result": str(result)[:200],
                                        })

                                await live_session.send_tool_response(
                                    function_responses=function_responses
                                )

                            # -- setup_complete --
                            if getattr(response, "setup_complete", None):
                                logger.info("Live API setup complete")

                    except Exception as e:
                        logger.error("Error in receive_responses: %s", e, exc_info=True)

                tasks = [
                    asyncio.create_task(send_audio_stream()),
                    asyncio.create_task(receive_responses()),
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error("Live API session error: %s", e, exc_info=True)
        finally:
            self.session_active = False
            self._live_session = None

    async def send_text(self, text: str):
        """Send text input using send_client_content (proper API)."""
        if not self._live_session or not self.session_active:
            logger.error("No active session")
            return
        try:
            await self._live_session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True,
            )
            logger.info("Sent text: %s", text[:50])
        except Exception as e:
            logger.error("Failed to send text: %s", e)

    async def send_audio_chunk(self, audio_data: bytes):
        """Queue audio data for streaming."""
        if self.session_active:
            await self.audio_queue.put(audio_data)

    async def signal_audio_stream_end(self):
        """Signal end of audio stream (user stopped speaking)."""
        if not self._live_session or not self.session_active:
            return
        try:
            await self._live_session.send_realtime_input(audio_stream_end=True)
            logger.info("Audio stream end signaled")
        except Exception as e:
            logger.error("Failed to signal audio_stream_end: %s", e)

    async def signal_activity(self, start: bool):
        """Signal user activity start/end for VAD hints."""
        if not self._live_session or not self.session_active:
            return
        try:
            if start:
                await self._live_session.send_realtime_input(activity_start=True)
            else:
                await self._live_session.send_realtime_input(activity_end=True)
        except Exception as e:
            logger.debug("Activity signal failed (may not be supported): %s", e)

    async def end_session(self):
        """End the Live API session."""
        self.session_active = False
        self._live_session = None
        logger.info("Live API session ended")


class ContinuousVoiceSession:
    """Manages a continuous voice conversation session."""

    def __init__(self, api_key: str):
        self.client = LiveAPIClient(api_key)
        self.is_speaking = False
        self._session_task = None

    async def start(self, websocket_callback, voice_name="Aoede",
                    system_instruction="", tools=None):
        """Start continuous conversation session.

        Args:
            websocket_callback: Async callable to send events to frontend.
            voice_name: Gemini voice preset.
            system_instruction: System prompt for the conversation.
            tools: List of (name, description, handler, parameters) tuples.
        """
        # Register tools if provided
        if tools:
            for name, desc, handler, params in tools:
                self.client.register_tool(name, desc, handler, params)

        async def handle_audio(audio_bytes):
            await websocket_callback({
                "type": "audio_chunk",
                "audio": base64.b64encode(audio_bytes).decode("utf-8"),
            })

        async def handle_text(text_event):
            await websocket_callback(text_event)

        self._session_task = asyncio.create_task(
            self.client.start_session(
                audio_callback=handle_audio,
                text_callback=handle_text,
                voice_name=voice_name,
                system_instruction=system_instruction,
            )
        )

        await asyncio.sleep(0.5)
        logger.info("Continuous voice session started")

    async def process_audio(self, audio_data: bytes):
        """Process incoming audio from user."""
        await self.client.send_audio_chunk(audio_data)

    async def process_text(self, text: str):
        """Process text input from user."""
        await self.client.send_text(text)

    async def stop_speaking(self):
        """Signal user stopped speaking."""
        await self.client.signal_audio_stream_end()

    async def stop(self):
        """Stop the continuous session."""
        await self.client.end_session()
        if self._session_task and not self._session_task.done():
            self._session_task.cancel()
        self._session_task = None
