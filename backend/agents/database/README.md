# Database Package

This package provides database connectivity and operations for the agent system.

## Structure

```
agents/database/
├── __init__.py                 # Package exports
├── README.md                   # This file
└── neo4j/                      # Neo4j graph database
    ├── __init__.py             # Neo4j package exports
    ├── service.py              # Core Neo4j service
    ├── indexes.py              # Index management
    ├── stats.py                # Database statistics
    └── queries.py              # Query templates
```

## Neo4j Integration

### Core Service
The `Neo4jService` class provides connection management and query execution:

```python
from agents.database.neo4j import get_neo4j_service, initialize_neo4j

# Initialize Neo4j on startup
initialize_neo4j()

# Get service instance
service = get_neo4j_service()

# Execute queries
result = service.execute_query("MATCH (n) RETURN count(n)")
```

### Configuration
Set environment variables:
- `NEO4J_URI`: Connection URI (default: `neo4j://127.0.0.1:7687`)
- `NEO4J_USER`: Username (default: `neo4j`)
- `NEO4J_PASSWORD`: Password (default: `11111111`)
- `NEO4J_DATABASE`: Database name (default: `neo4j`)

### Features

#### Automatic Indexing
The system automatically creates indexes for optimal performance:
- User and session indexes
- Agent indexes (slug, name, type)
- Conversation and message indexes
- Worker agent communication indexes

#### Query Templates
Pre-defined query templates in `queries.py`:
- Conversation management
- Agent management
- Worker communication
- Session management
- A2A protocol support

#### Statistics and Monitoring
Comprehensive database statistics:
- Node and relationship counts
- Agent-specific statistics
- Conversation metrics
- Performance monitoring

### Usage Examples

#### Basic Operations
```python
from agents.database.neo4j import get_neo4j_service
from agents.database.neo4j.queries import CONVERSATION_QUERIES

service = get_neo4j_service()

# Create a conversation
service.execute_write_query(
    CONVERSATION_QUERIES["create_conversation"],
    {
        "conversation_id": "conv_123",
        "session_id": "session_456",
        "timestamp": "2025-01-01T00:00:00"
    }
)
```

#### Statistics
```python
from agents.database.neo4j import get_database_stats

service = get_neo4j_service()
stats = get_database_stats(service)
print(f"Total nodes: {stats['total_nodes']}")
print(f"Active agents: {stats['agent_stats']['active_agents']}")
```

## Migration from Old Structure

The old `agents.services` module is deprecated. Update imports:

```python
# Old (deprecated)
from agents.services import Neo4jService, initialize_neo4j

# New (recommended)
from agents.database.neo4j import Neo4jService, initialize_neo4j
```

## Future Extensions

This structure supports easy addition of other databases:
- `agents/database/postgresql/` - For relational data
- `agents/database/redis/` - For caching
- `agents/database/elasticsearch/` - For search functionality

Each database package follows the same pattern:
- `service.py` - Core service class
- `__init__.py` - Package exports
- Additional modules for specific functionality