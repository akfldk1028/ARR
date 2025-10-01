"""
Voice Activity Detection (VAD) Module
Provides audio buffering and voice activity detection for accurate STT transcription
"""

from .base import VADBase, VADResult
from .silero_vad import SileroVAD
from .webrtc_vad import WebRTCVAD
from .audio_buffer import AudioBuffer
from .vad_config import VADConfig

__all__ = [
    'VADBase',
    'VADResult',
    'SileroVAD',
    'WebRTCVAD',
    'AudioBuffer',
    'VADConfig'
]
