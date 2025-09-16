"""
Agent Configuration
AI 에이전트 관련 설정을 관리합니다.
"""

import os
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class VoiceConfig:
    """음성 설정"""
    name: str
    language: str = 'en-US'
    description: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'language': self.language,
            'description': self.description
        }


@dataclass
class GeminiConfig:
    """Gemini 에이전트 설정"""
    model: str = 'gemini-2.5-flash-preview-native-audio-dialog'
    temperature: float = 0.9
    max_output_tokens: int = 2048

    # Text Settings
    text_instruction: str = (
        "You are a helpful AI assistant with multimodal capabilities. "
        "You can analyze images, video streams, and have natural conversations. "
        "Provide detailed and helpful responses. Be concise yet informative."
    )

    # Audio Settings
    audio_instruction: str = (
        "You are a helpful AI assistant with voice capabilities. "
        "Speak naturally and conversationally. Be friendly and engaging."
    )

    # Available Voices
    voices: List[VoiceConfig] = field(default_factory=lambda: [
        VoiceConfig('Aoede', 'en-US', 'Friendly and warm voice'),
        VoiceConfig('Charon', 'en-US', 'Deep and authoritative voice'),
        VoiceConfig('Fenrir', 'en-US', 'Energetic voice'),
        VoiceConfig('Kore', 'en-US', 'Calm and soothing voice'),
        VoiceConfig('Puck', 'en-US', 'Playful voice'),
    ])

    default_voice: str = 'Aoede'

    # Connection Settings
    connection_timeout: int = 30
    request_timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 1.0


class AgentConfig:
    """에이전트 설정 관리"""

    # API Keys
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

    # Agent Configurations
    AGENTS = {
        'gemini': GeminiConfig(
            model=os.getenv('GEMINI_MODEL', 'models/gemini-2.0-flash-exp'),
            temperature=float(os.getenv('GEMINI_TEMPERATURE', '0.9')),
            max_output_tokens=int(os.getenv('GEMINI_MAX_TOKENS', '2048')),
        ),
        # 향후 다른 에이전트 추가
        # 'gpt': GPTConfig(...),
        # 'claude': ClaudeConfig(...),
    }

    @classmethod
    def get_gemini_config(cls) -> GeminiConfig:
        """Gemini 설정 반환"""
        return cls.AGENTS['gemini']

    @classmethod
    def get_available_voices(cls) -> List[str]:
        """사용 가능한 음성 목록 반환"""
        gemini_config = cls.get_gemini_config()
        return [voice.name for voice in gemini_config.voices]

    @classmethod
    def get_voice_config(cls, voice_name: str) -> VoiceConfig:
        """특정 음성 설정 반환"""
        gemini_config = cls.get_gemini_config()
        for voice in gemini_config.voices:
            if voice.name == voice_name:
                return voice
        # 기본 음성 반환
        return gemini_config.voices[0]

    @classmethod
    def validate_api_keys(cls) -> Dict[str, bool]:
        """API 키 검증"""
        return {
            'google': bool(cls.GOOGLE_API_KEY and cls.GOOGLE_API_KEY != '...'),
            'openai': bool(cls.OPENAI_API_KEY and cls.OPENAI_API_KEY != '...'),
            'anthropic': bool(cls.ANTHROPIC_API_KEY and cls.ANTHROPIC_API_KEY != '...'),
        }