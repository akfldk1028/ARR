"""
Base VAD Interface
Abstract base class for Voice Activity Detection implementations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class VADResult:
    """Result from VAD processing"""
    is_speech: bool  # Whether speech was detected
    probability: float  # Confidence score (0.0-1.0)
    frame_index: int  # Frame index in the stream

    def __str__(self):
        return f"VADResult(speech={self.is_speech}, prob={self.probability:.2f}, frame={self.frame_index})"


class VADBase(ABC):
    """Abstract base class for Voice Activity Detection"""

    def __init__(self, sample_rate: int = 16000):
        """
        Initialize VAD

        Args:
            sample_rate: Audio sample rate (8000 or 16000 Hz)
        """
        if sample_rate not in [8000, 16000]:
            raise ValueError(f"Sample rate must be 8000 or 16000, got {sample_rate}")

        self.sample_rate = sample_rate
        self.frame_count = 0
        logger.info(f"Initialized {self.__class__.__name__} with sample_rate={sample_rate}")

    @abstractmethod
    def is_speech(self, audio_frame: bytes) -> VADResult:
        """
        Detect if audio frame contains speech

        Args:
            audio_frame: Raw audio data (16-bit PCM)

        Returns:
            VADResult with detection results
        """
        pass

    @abstractmethod
    def reset(self):
        """Reset VAD internal state"""
        pass

    def _validate_frame(self, audio_frame: bytes, expected_duration_ms: int):
        """
        Validate audio frame

        Args:
            audio_frame: Audio frame bytes
            expected_duration_ms: Expected frame duration in milliseconds
        """
        expected_size = int(self.sample_rate * expected_duration_ms / 1000) * 2  # 2 bytes per sample
        actual_size = len(audio_frame)

        if actual_size != expected_size:
            raise ValueError(
                f"Invalid frame size: expected {expected_size} bytes "
                f"for {expected_duration_ms}ms at {self.sample_rate}Hz, got {actual_size} bytes"
            )
