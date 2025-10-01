"""
Google Speech-to-Text Real-time Streaming Client
Provides real-time transcription for Korean voice input
"""

import asyncio
import base64
import logging
from typing import Optional, Callable
import os

logger = logging.getLogger(__name__)


class SpeechToTextClient:
    """Real-time Speech-to-Text client for Korean voice transcription"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Speech-to-Text client

        Args:
            api_key: Google Cloud API key (optional, can use GOOGLE_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        self.is_active = False
        self.recognition_client = None
        self.streaming_config = None
        self.transcript_callback = None

        # Buffer for accumulating audio chunks
        self.audio_buffer = []
        self.buffer_duration = 0.1  # Send every 100ms
        self.last_send_time = 0

    async def start_streaming(self, transcript_callback: Callable):
        """
        Start real-time streaming transcription

        Args:
            transcript_callback: Async function to call with transcription results
        """
        self.transcript_callback = transcript_callback
        self.is_active = True

        try:
            from google.cloud import speech

            # Initialize Speech-to-Text client (use sync client, not async)
            self.recognition_client = speech.SpeechClient()

            # Configure streaming recognition for Korean
            streaming_config = speech.StreamingRecognitionConfig(
                config=speech.RecognitionConfig(
                    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=16000,
                    language_code='ko-KR',  # Korean language
                    enable_automatic_punctuation=True
                ),
                interim_results=True,  # Get interim results for real-time feedback
                single_utterance=False  # Continue listening after pauses
            )

            self.streaming_config = streaming_config
            logger.info("Speech-to-Text streaming started for Korean (ko-KR)")

        except ImportError:
            logger.error("google-cloud-speech not installed. Install with: pip install google-cloud-speech")
            self.is_active = False
            raise
        except Exception as e:
            logger.error(f"Failed to start Speech-to-Text streaming: {e}")
            self.is_active = False
            raise

    async def process_audio_chunk(self, audio_data: str):
        """
        Process incoming audio chunk for transcription

        Args:
            audio_data: Base64-encoded audio data (PCM 16kHz)
        """
        if not self.is_active or not self.recognition_client:
            return

        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_data)

            # Add to buffer
            self.audio_buffer.append(audio_bytes)

            # Send to Speech-to-Text API when buffer is ready
            import time
            current_time = time.time()

            if (current_time - self.last_send_time) >= self.buffer_duration:
                await self._send_buffered_audio()
                self.last_send_time = current_time

        except Exception as e:
            logger.error(f"Error processing audio chunk for STT: {e}")

    async def _send_buffered_audio(self):
        """Send buffered audio to Speech-to-Text API"""
        if not self.audio_buffer:
            logger.debug("STT: No audio buffer, skipping")
            return

        try:
            from google.cloud import speech

            # Combine buffered audio
            combined_audio = b''.join(self.audio_buffer)
            self.audio_buffer.clear()

            logger.info(f"STT: Processing audio buffer ({len(combined_audio)} bytes)")

            # Skip if audio is too short or all zeros
            if len(combined_audio) < 100:
                logger.debug(f"STT: Audio too short ({len(combined_audio)} bytes), skipping")
                return

            # Check if audio is silent (first 1000 bytes sample)
            sample_size = min(1000, len(combined_audio))
            if all(b == 0 for b in combined_audio[:sample_size]):
                logger.debug("STT: Audio is silent, skipping")
                return

            # Create streaming request generator
            def request_generator():
                yield speech.StreamingRecognizeRequest(audio_content=combined_audio)

            # Process in thread to avoid blocking async loop
            def process_streaming():
                """Sync function to run in thread"""
                results = []
                try:
                    logger.info("STT: Sending audio to Google Speech-to-Text API...")

                    # Send to API and get response (correct parameter: config, not streaming_config)
                    responses = self.recognition_client.streaming_recognize(
                        config=self.streaming_config,
                        requests=request_generator()
                    )

                    logger.info("STT: Received response from API, processing...")

                    # Process responses (sync API)
                    for response in responses:
                        if not response.results:
                            continue

                        result = response.results[0]
                        if not result.alternatives:
                            continue

                        transcript = result.alternatives[0].transcript
                        is_final = result.is_final

                        logger.info(f"STT: Got transcript (final={is_final}): {transcript}")

                        if transcript.strip() and is_final:
                            results.append(transcript)
                            logger.info(f"STT Transcription (final): {transcript}")

                except Exception as e:
                    logger.error(f"Error in streaming recognize: {e}")

                return results

            # Run sync API in thread pool
            transcripts = await asyncio.to_thread(process_streaming)

            # Send final transcripts to callback
            for transcript in transcripts:
                if self.transcript_callback:
                    await self.transcript_callback(transcript)

        except Exception as e:
            logger.error(f"Error sending audio to STT API: {e}")

    async def stop_streaming(self):
        """Stop streaming transcription"""
        self.is_active = False

        # Send any remaining buffered audio
        if self.audio_buffer:
            await self._send_buffered_audio()

        self.recognition_client = None
        self.streaming_config = None
        logger.info("Speech-to-Text streaming stopped")


class SpeechToTextService:
    """Service wrapper for managing Speech-to-Text client lifecycle"""

    def __init__(self):
        self.client = None
        self.api_key = os.getenv('GOOGLE_API_KEY')

    async def start_session(self, transcript_callback: Callable):
        """Start a new STT session"""
        self.client = SpeechToTextClient(self.api_key)
        await self.client.start_streaming(transcript_callback)
        return self.client

    async def stop_session(self):
        """Stop current STT session"""
        if self.client:
            await self.client.stop_streaming()
            self.client = None