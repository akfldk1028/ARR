"""
VAD + STT Integrated Service
Combines Voice Activity Detection with Speech-to-Text for accurate transcription
"""

import asyncio
import base64
import logging
from typing import Optional, Callable
from .vad import SileroVAD, WebRTCVAD, AudioBuffer, VADConfig
from .speech_to_text_client import SpeechToTextClient

logger = logging.getLogger(__name__)


class VADSTTService:
    """
    Integrated VAD + STT Service
    Buffers audio with VAD, sends complete utterances to STT
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        vad_engine: str = 'silero',  # 'silero' or 'webrtc'
        vad_config: Optional[VADConfig] = None
    ):
        """
        Initialize VAD + STT service

        Args:
            api_key: Google Cloud API key
            vad_engine: VAD engine to use ('silero' or 'webrtc')
            vad_config: VAD configuration (uses default if None)
        """
        self.api_key = api_key
        self.vad_engine = vad_engine
        self.config = vad_config or VADConfig()

        # Components
        self.vad = None
        self.audio_buffer = None
        self.stt_client = None
        self.transcript_callback = None

        self.is_active = False

        logger.info(
            f"VADSTTService initialized: engine={vad_engine}, "
            f"sample_rate={self.config.sample_rate}Hz"
        )

    async def start(self, transcript_callback: Callable):
        """
        Start VAD + STT service

        Args:
            transcript_callback: Async callback for transcription results
        """
        self.transcript_callback = transcript_callback

        try:
            # Initialize VAD
            if self.vad_engine == 'silero':
                logger.info("Initializing Silero VAD...")
                self.vad = SileroVAD(
                    sample_rate=self.config.sample_rate,
                    threshold=self.config.silero_threshold
                )
            elif self.vad_engine == 'webrtc':
                logger.info("Initializing WebRTC VAD...")
                self.vad = WebRTCVAD(
                    sample_rate=self.config.sample_rate,
                    aggressiveness=self.config.webrtc_aggressiveness
                )
            else:
                raise ValueError(f"Unknown VAD engine: {self.vad_engine}")

            # Initialize Audio Buffer with speech_end callback
            self.audio_buffer = AudioBuffer(
                vad=self.vad,
                config=self.config,
                on_speech_end=self._on_speech_end
            )

            # Initialize STT client
            self.stt_client = SpeechToTextClient(self.api_key)

            self.is_active = True
            logger.info("VAD + STT service started")

        except Exception as e:
            logger.error(f"Failed to start VAD + STT service: {e}")
            self.is_active = False
            raise

    async def process_audio_chunk(self, audio_data: str):
        """
        Process audio chunk with VAD buffering

        Args:
            audio_data: Base64-encoded audio data (PCM 16kHz, 16-bit)
        """
        if not self.is_active:
            return

        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_data)

            # Check if audio is valid
            if len(audio_bytes) < 100:
                return

            # Process frame through VAD buffer
            await self.audio_buffer.process_frame(audio_bytes)

        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")

    async def _on_speech_end(self, buffered_audio: bytes):
        """
        Callback when speech segment ends (silence detected)
        Sends buffered audio to STT for transcription

        Args:
            buffered_audio: Complete audio segment
        """
        logger.info(f"Speech segment complete: {len(buffered_audio)} bytes")

        try:
            # Send to Speech-to-Text API
            transcript = await self._transcribe_audio(buffered_audio)

            if transcript:
                logger.info(f"STT Result: {transcript}")

                # Call user callback
                if self.transcript_callback:
                    await self.transcript_callback(transcript)

        except Exception as e:
            logger.error(f"Error processing speech segment: {e}")

    async def _transcribe_audio(self, audio_bytes: bytes) -> Optional[str]:
        """
        Transcribe audio using Google Speech-to-Text

        Args:
            audio_bytes: Audio data (PCM 16kHz, 16-bit)

        Returns:
            Transcribed text or None
        """
        try:
            from google.cloud import speech

            # Create recognition config
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.config.sample_rate,
                language_code='ko-KR',
                enable_automatic_punctuation=True
            )

            # Create audio object
            audio = speech.RecognitionAudio(content=audio_bytes)

            # Perform synchronous recognition
            response = await asyncio.to_thread(
                self.stt_client.recognition_client.recognize,
                config=config,
                audio=audio
            )

            # Extract transcript
            if response.results:
                result = response.results[0]
                if result.alternatives:
                    transcript = result.alternatives[0].transcript
                    confidence = result.alternatives[0].confidence
                    logger.info(f"STT confidence: {confidence:.2f}")
                    return transcript.strip()

            return None

        except Exception as e:
            logger.error(f"STT transcription error: {e}")
            return None

    async def stop(self):
        """Stop VAD + STT service"""
        self.is_active = False

        # Flush any remaining buffered audio
        if self.audio_buffer:
            await self.audio_buffer.force_flush()

        logger.info("VAD + STT service stopped")

    def get_buffer_state(self):
        """Get current buffer state for monitoring"""
        if self.audio_buffer:
            return self.audio_buffer.get_state()
        return None
