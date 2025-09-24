# A2A Worker Agent System - Developer Documentation

## Overview
Complete A2A (Agent-to-Agent) protocol implementation with LangGraph-based worker agents, Django backend, and Gemini Live API integration.

## Architecture Components

### 1. Agent System (`agents/`)

#### Core Models (`agents/models.py`)
- **Agent**: Main agent entity with capabilities, system prompts, metadata
- **Organization**: Agent grouping and categorization
- **Tag**: Agent labeling system

#### Worker Agents (`agents/worker_agents/`)
```
worker_agents/
├── base/
│   └── base_worker.py          # BaseWorkerAgent abstract class - COMPLETE
├── implementations/
│   ├── general_worker.py       # General assistant with A2A delegation - COMPLETE
│   └── flight_specialist_worker.py  # Flight booking specialist - COMPLETE
├── cards/
│   ├── general_worker_card.json     # Agent card specifications - COMPLETE
│   └── flight_specialist_card.json
├── worker_factory.py          # Factory pattern for worker creation - COMPLETE
├── worker_manager.py           # Worker lifecycle management - COMPLETE
└── agent_discovery.py          # LLM-based agent discovery service - COMPLETE
```

#### A2A Protocol (`agents/a2a_client.py`)
- **A2AAgentCard**: Agent card representation - COMPLETE
- **A2ACardResolver**: Agent discovery via `/.well-known/agent-card.json` - COMPLETE
- **A2AClient**: JSON-RPC 2.0 message client - COMPLETE
- **A2AAgentRegistry**: Agent registration system - COMPLETE

#### Database System (`agents/database/neo4j/`)
- **service.py**: Core Neo4j operations - COMPLETE
- **indexes.py**: Index management - COMPLETE
- **stats.py**: Database statistics - COMPLETE
- **queries.py**: Query templates - COMPLETE

#### Django Views (`agents/views.py`)
- **Agent Card Endpoints**: A2A standard `/.well-known/agent-card/{slug}.json` - COMPLETE
- **Chat Interface**: JSON-RPC 2.0 and regular JSON support - COMPLETE
- **Agent Management**: Status, list endpoints - COMPLETE

### 2. Gemini Integration (`gemini/`)

#### Live API (`gemini/services/`)
- **gemini_client.py**: Gemini Pro text generation - COMPLETE
- **live_api_client.py**: Gemini Live API for real-time audio - COMPLETE
- **websocket_live_client.py**: WebSocket client for Gemini Live - COMPLETE

#### WebSocket Consumer (`gemini/consumers/simple_consumer.py`)
- **Text/Audio Processing**: Handles user input via WebSocket - COMPLETE
- **A2A Integration**: Agent delegation with announcement system - COMPLETE
- **Voice Configuration**: Per-agent TTS voice settings - COMPLETE
- **Real-time Streaming**: Live audio/text streaming - COMPLETE

#### Templates (`gemini/templates/gemini/`)
- **index.html**: Main chat interface with A2A support - COMPLETE

### 3. Configuration (`config/`)

#### Agent Configuration (`config/agent_config.py`)
- **get_voice_config()**: Voice settings per agent - COMPLETE
  - test-agent: Aoede voice
  - flight-specialist: Kore voice
  - general-worker: Leda voice
  - Default: Charon voice

## Completed Features

### ✅ A2A Protocol Compliance
- JSON-RPC 2.0 message format
- Agent card discovery endpoints
- Bidirectional agent communication
- Standard `/.well-known/agent-card.json` endpoints

### ✅ Worker Agent Communication
- LLM-based delegation decisions
- Context-aware message routing
- Session and context ID tracking
- Multi-agent collaboration

### ✅ Voice Differentiation
- Per-agent TTS voice configuration
- Google Gemini voice models (Aoede, Kore, Leda, Charon)
- Voice switching during agent delegation

### ✅ Real-time Features
- WebSocket-based chat interface
- Live audio streaming with Gemini Live API
- Real-time agent delegation announcements
- Streaming text responses

### ✅ Database Integration
- Neo4j graph database for conversations
- Message persistence with metadata
- Agent relationship tracking
- Session management

## Key Code Files to Review

### For Agent System:
1. **`agents/worker_agents/implementations/general_worker.py`** - Main delegation logic
2. **`agents/worker_agents/agent_discovery.py`** - LLM-based agent selection
3. **`agents/a2a_client.py`** - A2A protocol implementation
4. **`agents/views.py`** - Django REST endpoints

### For A2A Protocol:
1. **`agents/views.py:AgentChatView`** - JSON-RPC 2.0 handler
2. **`agents/a2a_client.py:A2AClient.send_message()`** - Message format
3. **`agents/worker_agents/cards/*.json`** - Agent specifications

### For Live API Integration:
1. **`gemini/services/live_api_client.py`** - Live API connection
2. **`gemini/services/websocket_live_client.py`** - WebSocket client
3. **`gemini/consumers/simple_consumer.py`** - WebSocket consumer

### For Voice Configuration:
1. **`config/agent_config.py:get_voice_config()`** - Voice settings
2. **`gemini/consumers/simple_consumer.py`** - Voice switching logic

## Agent Delegation Flow

1. **User Request** → General Agent (test-agent)
2. **LLM Analysis** → AgentDiscoveryService determines if delegation needed
3. **Agent Selection** → Best specialist agent chosen
4. **Announcement** → "I'll ask our Flight Specialist agent to help..."
5. **A2A Communication** → JSON-RPC 2.0 message to specialist
6. **Response Coordination** → General agent formats combined response
7. **Voice Switching** → Response delivered in specialist's voice

## Testing Commands

```bash
# Create agents
python manage.py create_test_agent
python manage.py create_second_agent

# Test A2A communication
python manage.py test_worker_communication --source-agent test-agent --target-agent flight-specialist

# Run server
set OPENAI_API_KEY=your_key && set GOOGLE_API_KEY=your_key && daphne -p 8002 backend.asgi:application
```

## Endpoints

- **Main Interface**: `http://localhost:8002/gemini/`
- **Agent Cards**: `http://localhost:8002/agents/.well-known/agent-card/{slug}.json`
- **A2A Chat**: `http://localhost:8002/agents/{slug}/chat/` (JSON-RPC 2.0)
- **Agent List**: `http://localhost:8002/agents/list/`

## Development Status

### 🟢 Complete Features
- A2A protocol implementation
- Worker agent system
- Live API integration
- Voice differentiation
- WebSocket communication
- Neo4j integration
- LangGraph migration

### 🟡 In Progress
- (No current issues - Voice Conversation is fully functional)

### ✅ RECENTLY FIXED Issues (Current Session)
- **Voice Conversation Chat Display**: 🎙️ Voice Conversation transcript now shows in chat UI ✅
  - FIXED: Added missing `input_audio_transcription={}` and `output_audio_transcription={}` to Live API configuration
  - FIXED: Enhanced transcript handling in both `live_api_client.py` and `websocket_live_client.py`
  - FIXED: User transcripts display with `[USER]:` prefix handling
  - FIXED: AI transcripts display as assistant messages
  - FIXED: Agent-specific voice configuration for Voice Conversation sessions
  - FIXED: A2A delegation chat display in Voice Conversation with proper indentation
  - Files Fixed: `gemini/services/live_api_client.py`, `gemini/services/websocket_live_client.py`, `gemini/consumers/simple_consumer.py`

### 🟢 Voice Conversation Now Fully Working
- ✅ Transcript display in chat interface (both user and AI messages)
- ✅ A2A delegation announcements and responses in Voice Conversation
- ✅ Agent-specific voice switching during delegation
- ✅ Proper database persistence for voice conversation messages
- ✅ Real-time audio and text processing
- ✅ Context7-compliant Gemini Live API configuration

### ✅ FIXED Issues (Previous Session)
- Asyncio scope issues in Django views → Fixed with `async_to_sync` pattern
- Voice differentiation → Fixed with agent-specific voice mapping in `config/agent_config.py`
- Mock LLM usage → Fixed by ensuring real OpenAI API key usage
- Delegation announcements → Enhanced with prominent styling and A2A processing
- A2A timeout issues → Resolved with proper Django Channels async handling

## 🔧 Recent Work Completed (Current Session)

### ✅ Voice Conversation Transcript Problem SOLVED
- **Root Cause Found**: Missing transcript configuration in Gemini Live API setup
- **Solution**: Added `input_audio_transcription={}` and `output_audio_transcription={}` to Live API config
- **Files Fixed**:
  - `gemini/services/live_api_client.py`: Added transcript config and handling
  - `gemini/services/websocket_live_client.py`: Added transcript config and processing
  - `gemini/consumers/simple_consumer.py`: Enhanced A2A delegation with proper indentation

### ✅ Voice Conversation A2A Integration Complete
- **Feature**: Full A2A delegation support in Voice Conversation mode
- **Implementation**: User speech → transcript → A2A processing → specialist response with voice switching
- **Voice Configuration**: Agent-specific voices (test-agent: Aoede, flight-specialist: Kore, etc.)
- **Chat Display**: Both user and AI transcripts now show in chat interface with proper A2A announcements

### ✅ Context7 Research Success
- **Source**: Official Gemini Live API documentation and Context7 library patterns
- **Key Finding**: Transcript support requires explicit configuration in setup message
- **Implementation**: Proper JSON-RPC 2.0 format with transcript config fields

### Ready for Production
- Voice Conversation now fully functional with transcript display
- A2A delegation working in voice mode with specialist voice switching
- Server running on port 8003: `http://localhost:8003/gemini/`
- All known Voice Conversation issues resolved

## Architecture Highlights

- **Clean Separation**: Agents, protocol, and API integration are modular
- **Standards Compliance**: Full A2A protocol and JSON-RPC 2.0 support
- **Scalable Design**: Easy to add new agent types and capabilities
- **Real-time Ready**: WebSocket and streaming support throughout
- **Multi-modal**: Text and audio processing with voice differentiation
