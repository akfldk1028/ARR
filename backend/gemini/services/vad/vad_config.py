"""
VAD Configuration
Centralized configuration for Voice Activity Detection
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class VADConfig:
    """Configuration for Voice Activity Detection"""

    # VAD Engine Selection
    engine: Literal['silero', 'webrtc'] = 'silero'  # Silero for accuracy, WebRTC for speed

    # Audio Parameters
    sample_rate: int = 16000  # 16kHz for STT compatibility
    frame_duration_ms: int = 30  # Frame duration in milliseconds (10, 20, or 30)

    # Silence Detection
    silence_threshold: float = 0.5  # Probability threshold for speech (0.0-1.0)
    silence_duration_ms: int = 500  # Duration of silence to trigger buffer flush (ms)

    # Buffer Management
    min_speech_duration_ms: int = 300  # Minimum speech duration to send to STT
    max_speech_duration_ms: int = 10000  # Maximum buffer size (10 seconds)

    # WebRTC VAD Aggressiveness (0-3, higher = more aggressive filtering)
    webrtc_aggressiveness: int = 2

    # Silero VAD Parameters
    silero_threshold: float = 0.5  # Speech probability threshold

    @property
    def frame_size_samples(self) -> int:
        """Calculate frame size in samples"""
        return int(self.sample_rate * self.frame_duration_ms / 1000)

    @property
    def frame_size_bytes(self) -> int:
        """Calculate frame size in bytes (16-bit PCM)"""
        return self.frame_size_samples * 2  # 2 bytes per sample (16-bit)

    @property
    def silence_frames(self) -> int:
        """Number of consecutive silence frames to trigger flush"""
        return int(self.silence_duration_ms / self.frame_duration_ms)

    @property
    def min_speech_frames(self) -> int:
        """Minimum number of speech frames"""
        return int(self.min_speech_duration_ms / self.frame_duration_ms)

    @property
    def max_speech_frames(self) -> int:
        """Maximum number of speech frames"""
        return int(self.max_speech_duration_ms / self.frame_duration_ms)


# Default configuration
DEFAULT_VAD_CONFIG = VADConfig()
