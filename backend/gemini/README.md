# gemini

Google Gemini voice integration with Live API support.

## Models
- `ChatSession` - Voice/text session tracking (UUID, user, metadata)
- `ChatMessage` - Messages (text/image/audio/system, sender: user/assistant/system)

## Views
- `/gemini/` - Main chat interface
- `/gemini/continuous-voice/` - Continuous voice mode
- `/gemini/live-voice-a2a/` - Live voice with A2A routing
- `/gemini/health/` - Health check

## Structure
```
gemini/
├── models.py          # ChatSession, ChatMessage
├── views.py           # Voice/chat views
├── urls.py            # URL patterns
├── consumers/         # WebSocket consumers (Django Channels)
├── services/          # Gemini client, Live API, service manager
├── templates/         # HTML templates for voice UI
├── config/            # Local settings
└── examples/liveAPI/  # Gemini Live API examples
```

## Dependencies
- `config.agent_config` - Voice/model configuration
- `config.api_config` - API keys and endpoints
- Django Channels (ASGI)
- `GOOGLE_API_KEY` environment variable
