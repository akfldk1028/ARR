"""
WebRTC VAD Implementation
Lightweight, fast VAD using Google's WebRTC library
"""

import logging
from typing import Optional
from .base import VADBase, VADResult

logger = logging.getLogger(__name__)


class WebRTCVAD(VADBase):
    """WebRTC Voice Activity Detector"""

    def __init__(self, sample_rate: int = 16000, aggressiveness: int = 2):
        """
        Initialize WebRTC VAD

        Args:
            sample_rate: Audio sample rate (8000 or 16000 Hz)
            aggressiveness: VAD aggressiveness (0-3, higher = more aggressive)
        """
        super().__init__(sample_rate)

        try:
            import webrtcvad
            self.vad = webrtcvad.Vad(aggressiveness)
            logger.info(f"WebRTC VAD initialized with aggressiveness={aggressiveness}")
        except ImportError:
            logger.error("webrtcvad not installed. Install with: pip install webrtcvad")
            raise

        self.aggressiveness = aggressiveness

    def is_speech(self, audio_frame: bytes) -> VADResult:
        """
        Detect if audio frame contains speech

        Args:
            audio_frame: Raw audio data (16-bit PCM)

        Returns:
            VADResult with detection results
        """
        self.frame_count += 1

        try:
            # WebRTC VAD returns boolean
            is_speech = self.vad.is_speech(audio_frame, self.sample_rate)

            # WebRTC doesn't provide probability, so use binary confidence
            probability = 1.0 if is_speech else 0.0

            return VADResult(
                is_speech=is_speech,
                probability=probability,
                frame_index=self.frame_count
            )

        except Exception as e:
            logger.error(f"WebRTC VAD error: {e}")
            # Return non-speech on error to avoid false positives
            return VADResult(
                is_speech=False,
                probability=0.0,
                frame_index=self.frame_count
            )

    def reset(self):
        """Reset VAD internal state"""
        self.frame_count = 0
        logger.debug("WebRTC VAD reset")

    def set_aggressiveness(self, aggressiveness: int):
        """
        Set VAD aggressiveness mode

        Args:
            aggressiveness: 0 (least aggressive) to 3 (most aggressive)
        """
        if not 0 <= aggressiveness <= 3:
            raise ValueError(f"Aggressiveness must be 0-3, got {aggressiveness}")

        self.vad.set_mode(aggressiveness)
        self.aggressiveness = aggressiveness
        logger.info(f"WebRTC VAD aggressiveness set to {aggressiveness}")
