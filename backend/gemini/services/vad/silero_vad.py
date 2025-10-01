"""
Silero VAD Implementation
High-accuracy VAD using Silero's deep learning model
"""

import logging
import torch
import numpy as np
from typing import Optional
from .base import VADBase, VADResult

logger = logging.getLogger(__name__)


class SileroVAD(VADBase):
    """Silero Voice Activity Detector (Deep Learning)"""

    def __init__(self, sample_rate: int = 16000, threshold: float = 0.5):
        """
        Initialize Silero VAD

        Args:
            sample_rate: Audio sample rate (8000 or 16000 Hz)
            threshold: Speech probability threshold (0.0-1.0)
        """
        super().__init__(sample_rate)

        try:
            # Load Silero VAD model from torch hub
            self.model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )

            self.get_speech_timestamps = utils[0]
            self.save_audio = utils[1]
            self.read_audio = utils[2]
            self.VADIterator = utils[3]
            self.collect_chunks = utils[4]

            self.model.eval()
            logger.info(f"Silero VAD initialized with threshold={threshold}")

        except Exception as e:
            logger.error(f"Failed to load Silero VAD: {e}")
            logger.error("Install with: pip install torch torchaudio")
            raise

        self.threshold = threshold
        self.vad_iterator = self.VADIterator(
            model=self.model,
            threshold=threshold,
            sampling_rate=sample_rate,
            min_silence_duration_ms=100,
            speech_pad_ms=30
        )

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
            # Convert bytes to numpy array
            audio_int16 = np.frombuffer(audio_frame, dtype=np.int16)

            # Silero VAD requires exactly 512 samples for 16kHz
            required_samples = 512 if self.sample_rate == 16000 else 256

            # Resample if needed
            if len(audio_int16) != required_samples:
                # Pad with zeros if too short
                if len(audio_int16) < required_samples:
                    audio_int16 = np.pad(audio_int16, (0, required_samples - len(audio_int16)), mode='constant')
                # Truncate if too long
                else:
                    audio_int16 = audio_int16[:required_samples]

            # Normalize to float32 [-1.0, 1.0]
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio_float32)

            # Get speech probability
            with torch.no_grad():
                speech_dict = self.vad_iterator(audio_tensor, return_seconds=False)

            # Extract probability
            if speech_dict:
                probability = float(speech_dict.get('speech_prob', 0.0))
            else:
                probability = 0.0

            is_speech = probability >= self.threshold

            return VADResult(
                is_speech=is_speech,
                probability=probability,
                frame_index=self.frame_count
            )

        except Exception as e:
            logger.error(f"Silero VAD error: {e}")
            # Return non-speech on error
            return VADResult(
                is_speech=False,
                probability=0.0,
                frame_index=self.frame_count
            )

    def reset(self):
        """Reset VAD internal state"""
        self.frame_count = 0
        self.vad_iterator.reset_states()
        logger.debug("Silero VAD reset")

    def set_threshold(self, threshold: float):
        """
        Set speech probability threshold

        Args:
            threshold: 0.0 to 1.0
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be 0.0-1.0, got {threshold}")

        self.threshold = threshold
        self.vad_iterator.threshold = threshold
        logger.info(f"Silero VAD threshold set to {threshold}")
