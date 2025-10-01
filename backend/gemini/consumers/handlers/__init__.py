"""
Consumer Handlers Package

This package contains specialized handlers for different types of WebSocket consumer operations:

- utils: Common utility functions for all handlers
- message_handler: General message processing (text, audio, image)
- live_api_handler: Live API voice session handling
- a2a_handler: Agent-to-Agent communication and routing
- agent_handler: Agent management and switching
"""

from .utils import safe_log_text, estimate_tts_duration, format_error_message, validate_audio_data
from .message_handler import MessageHandler
from .live_api_handler import LiveAPIHandler
from .a2a_handler import A2AHandler
from .agent_handler import AgentHandler

__all__ = [
    'safe_log_text',
    'estimate_tts_duration',
    'format_error_message',
    'validate_audio_data',
    'MessageHandler',
    'LiveAPIHandler',
    'A2AHandler',
    'AgentHandler'
]