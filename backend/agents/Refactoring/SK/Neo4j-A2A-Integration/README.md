# Neo4j + A2A Integration Project

## 🎯 Project Overview
This project integrates Neo4j Graph Database with Agent-to-Agent (A2A) Protocol to create an intelligent multi-agent conversation tracking and optimization system.

## 📁 Project Structure
```
Neo4j-A2A-Integration/
├── agents/              # A2A Agent implementations
├── graph/              # Neo4j database operations
├── models/             # Data models and schemas
├── utils/              # Utility functions
├── tests/              # Test files
├── logs/               # Log files
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## 🎭 Key Features
- **Real-time Conversation Tracking**: Store all agent interactions in Neo4j
- **Pattern Analysis**: Analyze conversation patterns for optimization
- **Smart Routing**: Intelligent agent routing based on historical data
- **Relationship Mapping**: Visual representation of agent interactions
- **Performance Analytics**: Track response times and success rates

## 🚀 Getting Started
1. Install dependencies: `pip install -r requirements.txt`
2. Start Neo4j database
3. Configure database connection in `.env`
4. Run the main application

## 📊 Graph Schema
- **User**: Represents conversation participants
- **Agent**: A2A-enabled agents
- **Conversation**: Individual conversation sessions
- **Message**: Individual messages in conversations
- **Relationship Types**: ASKS, RESPONDS, DELEGATES_TO, HANDLED_BY

## 🔧 Technologies
- Python 3.9+
- Neo4j Graph Database
- Semantic Kernel
- A2A Protocol (Agent-to-Agent)
- FastAPI (for REST endpoints)
- Uvicorn (ASGI server)