# config

Shared configuration for AI agent settings and API keys.

## Files
- `agent_config.py` - `AgentConfig`, `GeminiConfig`, `VoiceConfig` (model, temperature, voices)
- `api_config.py` - `APIConfig`, `APIEndpoint` (keys, endpoints, rate limits)
- `app_settings.py` - Application-level settings

## Usage
```python
from config.agent_config import AgentConfig, GeminiConfig
from config.api_config import APIConfig
```

## Environment Variables
- `GOOGLE_API_KEY` - Gemini API
- `OPENAI_API_KEY` - OpenAI API
- `ANTHROPIC_API_KEY` - Claude API
- `GEMINI_MODEL` - Model name (default: gemini-live-2.5-flash-preview)

## Note
NOT a Django app (no models/views). Pure configuration package used by `gemini/`.
