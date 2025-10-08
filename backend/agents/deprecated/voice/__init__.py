"""
A2A Voice Module - Real-time voice integration with Gemini Live API
Enables voice conversations with A2A agent system using different voices per agent
"""

from .a2a_voice_service import A2AVoiceService, get_voice_service
from .websocket_server import run_voice_server, voice_manager

__all__ = [
    'A2AVoiceService',
    'get_voice_service',
    'run_voice_server',
    'voice_manager'
]