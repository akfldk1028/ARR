# graph_db

Neo4j graph database algorithms and CDC (Change Data Capture) integration.

## Structure
```
graph_db/
├── algorithms/        # Graph algorithms
│   ├── core/          # PageRank, community detection, centrality
│   ├── domain/        # Domain-specific graph queries
│   └── repository/    # Data access layer
├── services/          # Neo4j service layer
├── schema/            # Graph schema definitions
├── realtime/          # CDC event handling, Kafka integration
└── tracking/          # Graph change tracking
```

## Key Features
- Graph algorithms (PageRank, community detection)
- CDC event handler for real-time graph sync
- Kafka producer integration for event streaming

## Dependencies
- Neo4j (bolt://localhost:7687)
- Kafka (optional, for CDC events)

## Note
NOT a Django app. Utility package for graph operations.
Used by `law/` pipeline and `agents/database/neo4j/`.
