"""
Audio Buffer with VAD
Buffers audio frames until silence is detected, then flushes for STT processing
"""

import asyncio
import logging
from typing import Optional, Callable, List
from dataclasses import dataclass
from .base import VADBase, VADResult
from .vad_config import VADConfig

logger = logging.getLogger(__name__)


@dataclass
class BufferState:
    """Current state of the audio buffer"""
    is_active: bool = False  # Whether buffering is active
    speech_frames: int = 0  # Number of speech frames in buffer
    silence_frames: int = 0  # Consecutive silence frames
    total_frames: int = 0  # Total frames processed
    buffer_size_bytes: int = 0  # Current buffer size in bytes


class AudioBuffer:
    """
    Audio buffer with Voice Activity Detection
    Accumulates audio frames until silence is detected
    """

    def __init__(
        self,
        vad: VADBase,
        config: VADConfig,
        on_speech_end: Optional[Callable] = None
    ):
        """
        Initialize audio buffer

        Args:
            vad: VAD instance for speech detection
            config: VAD configuration
            on_speech_end: Async callback when speech segment ends (receives buffered audio)
        """
        self.vad = vad
        self.config = config
        self.on_speech_end = on_speech_end

        # Buffer state
        self.buffer: List[bytes] = []
        self.state = BufferState()

        logger.info(
            f"AudioBuffer initialized: "
            f"min_speech={config.min_speech_duration_ms}ms, "
            f"silence={config.silence_duration_ms}ms, "
            f"max_buffer={config.max_speech_duration_ms}ms"
        )

    async def process_frame(self, audio_frame: bytes) -> Optional[VADResult]:
        """
        Process audio frame with VAD

        Args:
            audio_frame: Raw audio frame (16-bit PCM)

        Returns:
            VADResult if processed, None if frame invalid
        """
        try:
            # Run VAD on frame
            vad_result = self.vad.is_speech(audio_frame)

            self.state.total_frames += 1

            if vad_result.is_speech:
                # Speech detected
                await self._handle_speech_frame(audio_frame, vad_result)
            else:
                # Silence detected
                await self._handle_silence_frame(audio_frame, vad_result)

            # Check max buffer size
            if self.state.speech_frames >= self.config.max_speech_frames:
                logger.warning(
                    f"Max buffer size reached ({self.config.max_speech_duration_ms}ms), "
                    "forcing flush"
                )
                await self._flush_buffer(force=True)

            return vad_result

        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            return None

    async def _handle_speech_frame(self, audio_frame: bytes, vad_result: VADResult):
        """Handle frame with detected speech"""
        # Add to buffer
        self.buffer.append(audio_frame)
        self.state.buffer_size_bytes += len(audio_frame)
        self.state.speech_frames += 1
        self.state.silence_frames = 0

        # Activate buffer if not active
        if not self.state.is_active:
            self.state.is_active = True
            logger.info(
                f"Speech started (prob={vad_result.probability:.2f}, "
                f"frame={vad_result.frame_index})"
            )

    async def _handle_silence_frame(self, audio_frame: bytes, vad_result: VADResult):
        """Handle frame with detected silence"""
        if self.state.is_active:
            # Add silence frame to buffer (for natural trailing)
            self.buffer.append(audio_frame)
            self.state.buffer_size_bytes += len(audio_frame)
            self.state.silence_frames += 1

            # Check if silence duration threshold reached
            if self.state.silence_frames >= self.config.silence_frames:
                logger.info(
                    f"Silence detected for {self.config.silence_duration_ms}ms, "
                    f"flushing buffer"
                )
                await self._flush_buffer()

    async def _flush_buffer(self, force: bool = False):
        """
        Flush buffer and send to callback

        Args:
            force: Force flush even if min duration not met
        """
        if not self.buffer:
            return

        # Check minimum speech duration
        if not force and self.state.speech_frames < self.config.min_speech_frames:
            logger.debug(
                f"Speech too short ({self.state.speech_frames} frames, "
                f"min={self.config.min_speech_frames}), discarding"
            )
            self._reset_buffer()
            return

        # Combine all frames
        combined_audio = b''.join(self.buffer)
        buffer_duration_ms = (
            len(self.buffer) * self.config.frame_duration_ms
        )

        logger.info(
            f"Flushing buffer: {len(self.buffer)} frames, "
            f"{self.state.buffer_size_bytes} bytes, "
            f"{buffer_duration_ms}ms duration"
        )

        # Send to callback
        if self.on_speech_end:
            try:
                await self.on_speech_end(combined_audio)
            except Exception as e:
                logger.error(f"Error in speech_end callback: {e}")

        # Reset buffer
        self._reset_buffer()

    def _reset_buffer(self):
        """Clear buffer and reset state"""
        self.buffer.clear()
        self.state = BufferState()
        logger.debug("Buffer reset")

    async def force_flush(self):
        """Force flush buffer (for session end)"""
        if self.buffer:
            logger.info("Force flushing buffer")
            await self._flush_buffer(force=True)

    def get_state(self) -> BufferState:
        """Get current buffer state"""
        return self.state

    def reset(self):
        """Reset buffer and VAD"""
        self._reset_buffer()
        self.vad.reset()
        logger.info("AudioBuffer reset")
