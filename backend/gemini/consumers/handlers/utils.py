"""
Consumer Utilities - Common helper functions for WebSocket consumers
"""

import logging

logger = logging.getLogger('gemini.consumers')


def safe_log_text(text: str) -> str:
    """Safely encode text for logging, handling all encoding errors"""
    if not text:
        return text
    try:
        # Try to encode to UTF-8 first
        text.encode('utf-8')
        return text
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Replace problematic characters with ASCII backslash representation
        return text.encode('ascii', errors='backslashreplace').decode('ascii')


def estimate_tts_duration(text: str) -> float:
    """Estimate TTS playback duration based on text length"""
    if not text:
        return 0.0

    # Rough estimation: 80ms per character (Korean + English mixed)
    return len(text) * 0.08


def format_error_message(error: Exception, context: str = "") -> str:
    """Format error message for consistent logging"""
    error_msg = str(error)
    if context:
        return f"{context}: {error_msg}"
    return error_msg


def validate_audio_data(audio_data: str) -> bool:
    """Validate base64 audio data"""
    if not audio_data:
        return False

    try:
        import base64
        audio_bytes = base64.b64decode(audio_data)
        # Basic size validation (100 bytes to 50KB)
        if len(audio_bytes) < 100 or len(audio_bytes) > 50000:
            return False
        return True
    except Exception:
        return False