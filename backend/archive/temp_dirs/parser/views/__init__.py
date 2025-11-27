"""
Parser views package.

This package contains all API endpoints organized by functionality.
All 29 endpoints have been migrated from FastAPI score.py to Django REST Framework.

Modules:
- helpers: Common helper functions and constants
- health: Connection & health check endpoints (2)
- documents: Document management endpoints (5)
- schema: Graph schema endpoints (3)
- graph: Graph operations endpoints (8)
- extraction: Extraction & processing endpoints (5)
- chat: Chat bot endpoints (2)
- vector: Vector index & backend configuration endpoints (2)
- metrics: Evaluation metrics endpoints (2)
"""

# Import all endpoints from each module
from .health import (
    health,
    connect,
)

from .documents import (
    sources_list,
    upload,
    url_scan,
    delete_document_and_entities,
    document_status,
)

from .schema import (
    schema,
    populate_graph_schema,
    schema_visualization,
)

from .graph import (
    get_neighbours,
    chunk_entities,
    graph_query,
    fetch_chunktext,
    get_unconnected_nodes_list,
    delete_unconnected_nodes,
    get_duplicate_nodes,
    merge_duplicate_nodes,
)

from .extraction import (
    extract,
    post_processing,
    retry_processing,
    cancelled_job,
    update_extract_status,
)

from .chat import (
    chat_bot,
    clear_chat_bot,
)

from .vector import (
    drop_create_vector_index,
    backend_connection_configuration,
)

from .metrics import (
    calculate_metric,
    calculate_additional_metrics,
)

# Export all endpoints
__all__ = [
    # Health (2)
    'health',
    'connect',

    # Documents (5)
    'sources_list',
    'upload',
    'url_scan',
    'delete_document_and_entities',
    'document_status',

    # Schema (3)
    'schema',
    'populate_graph_schema',
    'schema_visualization',

    # Graph (8)
    'get_neighbours',
    'chunk_entities',
    'graph_query',
    'fetch_chunktext',
    'get_unconnected_nodes_list',
    'delete_unconnected_nodes',
    'get_duplicate_nodes',
    'merge_duplicate_nodes',

    # Extraction (5)
    'extract',
    'post_processing',
    'retry_processing',
    'cancelled_job',
    'update_extract_status',

    # Chat (2)
    'chat_bot',
    'clear_chat_bot',

    # Vector (2)
    'drop_create_vector_index',
    'backend_connection_configuration',

    # Metrics (2)
    'calculate_metric',
    'calculate_additional_metrics',
]
