# DomainManager - Comprehensive Guide

## Overview

The `DomainManager` is a centralized domain discovery and metadata service that provides:

1. **Domain Discovery**: Query Neo4j for all Domain nodes
2. **Intelligent Caching**: Cache domain list with configurable TTL-based refresh
3. **Metadata Access**: Provide rich domain metadata (domain_id, domain_name, description, etc.)
4. **Change Detection**: Automatically detect when domains are added/removed
5. **Event System**: Observable pattern for domain change notifications
6. **Thread Safety**: Safe concurrent access from multiple threads

---

## Architecture

### Design Patterns

1. **Singleton Pattern**: Global single instance across application
2. **Cache-Aside Pattern**: Load-through cache with TTL-based invalidation
3. **Observer Pattern**: Event-driven change notifications
4. **Repository Pattern**: Abstraction over Neo4j data access

### Key Components

```
DomainManager
├── Domain Cache (Dict[str, DomainMetadata])
├── Change Detection (Set comparison)
├── Event System (List[Callable])
└── Neo4j Service (Data source)
```

---

## Quick Start

### Basic Usage

```python
from agents.law.domain_manager import DomainManager

# Get singleton instance
manager = DomainManager.get_instance()

# Get all domains
domains = manager.get_all_domains()
for domain in domains:
    print(f"{domain.domain_name}: {domain.node_count} nodes")

# Get specific domain
domain = manager.get_domain("domain_abc123")
if domain:
    print(f"Found: {domain.domain_name}")
```

### With Configuration

```python
from agents.law.domain_manager import DomainManager
from graph_db.services import Neo4jService

# Custom Neo4j service
neo4j = Neo4jService(uri="neo4j://localhost:7687")

# Create with custom settings
manager = DomainManager.get_instance(
    neo4j_service=neo4j,
    cache_ttl_seconds=600,  # 10 minutes
    auto_refresh=True
)
```

---

## API Reference

### DomainManager Class

#### `get_instance(neo4j_service=None, cache_ttl_seconds=300, auto_refresh=True)`

Get or create singleton instance.

**Parameters:**
- `neo4j_service` (Neo4jService, optional): Neo4j service instance
- `cache_ttl_seconds` (int, default=300): Cache time-to-live in seconds
- `auto_refresh` (bool, default=True): Enable automatic refresh

**Returns:** DomainManager instance

**Example:**
```python
manager = DomainManager.get_instance(cache_ttl_seconds=600)
```

---

#### `get_all_domains(force_refresh=False)`

Get all domains from cache or Neo4j.

**Parameters:**
- `force_refresh` (bool, default=False): Force refresh from Neo4j

**Returns:** List[DomainMetadata]

**Example:**
```python
# Get from cache (or refresh if expired)
domains = manager.get_all_domains()

# Force fresh data from Neo4j
domains = manager.get_all_domains(force_refresh=True)
```

---

#### `get_domain(domain_id, force_refresh=False)`

Get specific domain by ID.

**Parameters:**
- `domain_id` (str): Domain ID to retrieve
- `force_refresh` (bool, default=False): Force refresh

**Returns:** DomainMetadata or None

**Example:**
```python
domain = manager.get_domain("domain_abc123")
if domain:
    print(f"Domain: {domain.domain_name}")
    print(f"Nodes: {domain.node_count}")
    print(f"Last queried: {domain.last_queried}")
```

---

#### `get_domain_by_name(domain_name, force_refresh=False)`

Get domain by name.

**Parameters:**
- `domain_name` (str): Domain name to search
- `force_refresh` (bool, default=False): Force refresh

**Returns:** DomainMetadata or None

**Example:**
```python
domain = manager.get_domain_by_name("도시계획")
```

---

#### `get_domain_by_slug(agent_slug, force_refresh=False)`

Get domain by agent slug.

**Parameters:**
- `agent_slug` (str): Agent slug (e.g., "law_도시계획")
- `force_refresh` (bool, default=False): Force refresh

**Returns:** DomainMetadata or None

**Example:**
```python
domain = manager.get_domain_by_slug("law_urban_planning")
```

---

#### `refresh()`

Force refresh from Neo4j.

**Returns:** Dict with refresh statistics

**Example:**
```python
stats = manager.refresh()
print(f"Domains: {stats['domain_count']}")
print(f"Added: {stats['domains_added']}")
print(f"Removed: {stats['domains_removed']}")
```

---

#### `invalidate_cache()`

Invalidate cache (will refresh on next access).

**Example:**
```python
manager.invalidate_cache()
# Next access will trigger Neo4j refresh
```

---

#### `get_domain_count()`

Get total domain count.

**Returns:** int

**Example:**
```python
count = manager.get_domain_count()
print(f"Total domains: {count}")
```

---

#### `get_active_domains()`

Get only active domains.

**Returns:** List[DomainMetadata]

**Example:**
```python
active_domains = manager.get_active_domains()
```

---

#### `get_cache_info()`

Get cache statistics.

**Returns:** Dict with cache info

**Example:**
```python
cache_info = manager.get_cache_info()
print(f"Valid: {cache_info['is_valid']}")
print(f"Expired: {cache_info['is_expired']}")
print(f"Last refresh: {cache_info['last_refresh']}")
```

---

#### `add_change_listener(listener)`

Add domain change event listener.

**Parameters:**
- `listener` (Callable[[DomainChangeEvent], None]): Callback function

**Example:**
```python
def on_domain_change(event):
    print(f"Domain {event.change_type.value}: {event.domain_name}")

manager.add_change_listener(on_domain_change)
```

---

#### `remove_change_listener(listener)`

Remove domain change event listener.

**Parameters:**
- `listener` (Callable): Callback to remove

**Example:**
```python
manager.remove_change_listener(on_domain_change)
```

---

### DomainMetadata Class

Represents a single domain with metadata.

#### Fields

- `domain_id` (str): Unique domain identifier
- `domain_name` (str): Human-readable domain name
- `agent_slug` (str): Agent slug for URL routing
- `node_count` (int): Number of HANG nodes in domain
- `created_at` (datetime): Domain creation timestamp
- `updated_at` (datetime): Last update timestamp
- `centroid_embedding` (List[float], optional): Domain centroid vector
- `description` (str, optional): Domain description
- `is_active` (bool): Active status
- `last_queried` (datetime, optional): Last query timestamp
- `query_count` (int): Total query count

#### Methods

**`to_dict()`**: Convert to dictionary

```python
domain_dict = domain.to_dict()
print(domain_dict)
# {
#   'domain_id': 'domain_abc123',
#   'domain_name': '도시계획',
#   'node_count': 245,
#   ...
# }
```

**`from_neo4j_record(record)`**: Create from Neo4j result (class method)

```python
# Internally used by DomainManager
domain = DomainMetadata.from_neo4j_record(neo4j_record)
```

---

### DomainChangeEvent Class

Represents a domain change event.

#### Fields

- `change_type` (DomainChangeType): Type of change (ADDED/REMOVED/UPDATED)
- `domain_id` (str): Domain ID
- `domain_name` (str): Domain name
- `timestamp` (datetime): Event timestamp
- `metadata` (Dict, optional): Additional metadata

---

### DomainChangeType Enum

```python
class DomainChangeType(Enum):
    ADDED = "added"
    REMOVED = "removed"
    UPDATED = "updated"
```

---

## Usage Examples

### Example 1: Basic Domain Listing

```python
from agents.law.domain_manager import DomainManager

manager = DomainManager.get_instance()

# Get all domains
domains = manager.get_all_domains()

print(f"Total domains: {len(domains)}")
for domain in domains:
    print(f"\nDomain: {domain.domain_name}")
    print(f"  ID: {domain.domain_id}")
    print(f"  Nodes: {domain.node_count}")
    print(f"  Created: {domain.created_at.strftime('%Y-%m-%d %H:%M')}")
```

**Output:**
```
Total domains: 5

Domain: 도시계획
  ID: domain_abc123
  Nodes: 245
  Created: 2025-01-15 10:30

Domain: 건축규제
  ID: domain_def456
  Nodes: 187
  Created: 2025-01-15 10:31
...
```

---

### Example 2: Domain Lookup with Error Handling

```python
def get_domain_safe(domain_id: str) -> Optional[DomainMetadata]:
    """Safely get domain with error handling"""
    try:
        manager = DomainManager.get_instance()
        domain = manager.get_domain(domain_id)

        if domain:
            logger.info(f"Found domain: {domain.domain_name}")
            return domain
        else:
            logger.warning(f"Domain not found: {domain_id}")
            return None

    except Exception as e:
        logger.error(f"Error fetching domain: {e}")
        return None

# Usage
domain = get_domain_safe("domain_abc123")
if domain:
    print(f"Working with: {domain.domain_name}")
```

---

### Example 3: Change Detection with Notifications

```python
from agents.law.domain_manager import DomainManager, DomainChangeEvent

# Setup manager
manager = DomainManager.get_instance()

# Track changes
change_history = []

def domain_change_handler(event: DomainChangeEvent):
    """Handle domain change events"""
    change_history.append(event)

    if event.change_type.value == "added":
        print(f"✅ New domain added: {event.domain_name}")
        # Trigger domain agent creation
        create_domain_agent(event.domain_id)

    elif event.change_type.value == "removed":
        print(f"❌ Domain removed: {event.domain_name}")
        # Cleanup domain agent
        cleanup_domain_agent(event.domain_id)

# Register listener
manager.add_change_listener(domain_change_handler)

# Monitor for changes
import time
while True:
    stats = manager.refresh()
    if stats['domains_added'] > 0 or stats['domains_removed'] > 0:
        print(f"Changes detected: +{stats['domains_added']} -{stats['domains_removed']}")

    time.sleep(60)  # Check every minute
```

---

### Example 4: Integration with QueryCoordinator

```python
from agents.law.domain_manager import DomainManager
from agents.law.query_coordinator import QueryCoordinator

class EnhancedQueryCoordinator(QueryCoordinator):
    """QueryCoordinator with DomainManager integration"""

    def __init__(self):
        super().__init__()
        self.domain_manager = DomainManager.get_instance()

    def get_available_domains(self) -> List[str]:
        """Get list of available domain names"""
        domains = self.domain_manager.get_all_domains()
        return [d.domain_name for d in domains if d.is_active]

    def get_domain_agent(self, domain_name: str):
        """Get DomainAgent instance by name"""
        domain = self.domain_manager.get_domain_by_name(domain_name)
        if domain:
            # Get agent instance from AgentManager
            return self.agent_manager.get_agent_instance(domain.domain_id)
        return None

    async def route_query(self, query: str):
        """Route query to appropriate domain agent"""
        # Get all active domains
        domains = self.domain_manager.get_active_domains()

        # Find best domain using LLM
        best_domain = await self.select_domain(query, domains)

        # Get agent and execute
        agent = self.get_domain_agent(best_domain.domain_name)
        return await agent.execute(query)
```

---

### Example 5: Cache Management Strategy

```python
from agents.law.domain_manager import DomainManager
import threading
import time

# Strategy 1: Periodic Background Refresh
def background_refresh_worker(interval_seconds: int = 300):
    """Background thread to refresh domain cache"""
    manager = DomainManager.get_instance()

    while True:
        try:
            stats = manager.refresh()
            logger.info(f"Background refresh: {stats}")
        except Exception as e:
            logger.error(f"Background refresh error: {e}")

        time.sleep(interval_seconds)

# Start background refresh
refresh_thread = threading.Thread(
    target=background_refresh_worker,
    args=(300,),  # Every 5 minutes
    daemon=True
)
refresh_thread.start()

# Strategy 2: Invalidate on Domain Creation/Deletion
class DomainLifecycleHook:
    """Hook into domain lifecycle events"""

    @staticmethod
    def on_domain_created(domain_id: str):
        """Called when new domain created"""
        manager = DomainManager.get_instance()
        manager.invalidate_cache()
        logger.info(f"Cache invalidated due to domain creation: {domain_id}")

    @staticmethod
    def on_domain_deleted(domain_id: str):
        """Called when domain deleted"""
        manager = DomainManager.get_instance()
        manager.invalidate_cache()
        logger.info(f"Cache invalidated due to domain deletion: {domain_id}")
```

---

### Example 6: Statistics and Monitoring

```python
from agents.law.domain_manager import DomainManager
import json

def print_domain_statistics():
    """Print comprehensive domain statistics"""
    manager = DomainManager.get_instance()

    # Get all domains
    domains = manager.get_all_domains()

    # Basic stats
    print(f"Total Domains: {len(domains)}")
    print(f"Active Domains: {len(manager.get_active_domains())}")

    # Node distribution
    total_nodes = sum(d.node_count for d in domains)
    print(f"\nTotal Nodes: {total_nodes}")
    print(f"Average Nodes per Domain: {total_nodes / len(domains):.1f}")

    # Top domains by size
    print("\nTop 5 Largest Domains:")
    sorted_domains = sorted(domains, key=lambda d: d.node_count, reverse=True)
    for i, domain in enumerate(sorted_domains[:5], 1):
        print(f"  {i}. {domain.domain_name}: {domain.node_count} nodes")

    # Query statistics
    queried_domains = [d for d in domains if d.query_count > 0]
    if queried_domains:
        print(f"\nQuery Statistics:")
        print(f"  Queried Domains: {len(queried_domains)}")
        total_queries = sum(d.query_count for d in queried_domains)
        print(f"  Total Queries: {total_queries}")

        print("\n  Most Queried Domains:")
        sorted_by_queries = sorted(
            queried_domains,
            key=lambda d: d.query_count,
            reverse=True
        )
        for i, domain in enumerate(sorted_by_queries[:5], 1):
            print(f"    {i}. {domain.domain_name}: {domain.query_count} queries")

    # Cache info
    cache_info = manager.get_cache_info()
    print(f"\nCache Info:")
    print(f"  Valid: {cache_info['is_valid']}")
    print(f"  Expired: {cache_info['is_expired']}")
    print(f"  Last Refresh: {cache_info['last_refresh']}")

# Run statistics
print_domain_statistics()
```

---

## Neo4j Query Patterns

The DomainManager uses optimized Neo4j queries:

### Query 1: Load All Domains

```cypher
MATCH (d:Domain)
OPTIONAL MATCH (h:HANG)-[:BELONGS_TO_DOMAIN]->(d)
WITH d, count(h) as actual_node_count
RETURN d.domain_id AS domain_id,
       d.domain_name AS domain_name,
       d.agent_slug AS agent_slug,
       d.node_count AS stored_node_count,
       actual_node_count,
       d.centroid_embedding AS centroid_embedding,
       d.description AS description,
       d.created_at AS created_at,
       d.updated_at AS updated_at
ORDER BY d.domain_name
```

**Features:**
- Single efficient query
- Calculates actual node count
- Returns all metadata
- Ordered for consistent results

---

## Performance Considerations

### Cache Efficiency

- **First Access**: ~100-500ms (Neo4j query)
- **Cached Access**: <1ms (in-memory lookup)
- **Speedup**: 100-500x faster

### Memory Usage

- **Per Domain**: ~1-2 KB (without centroid embedding)
- **With Embedding**: ~4-6 KB (768-dim float array)
- **100 Domains**: ~400-600 KB total

### Recommendations

1. **Cache TTL**: Set based on domain volatility
   - High volatility: 60-300s
   - Low volatility: 300-900s
   - Stable system: 900-3600s

2. **Refresh Strategy**:
   - Background refresh for critical systems
   - On-demand refresh for development
   - Event-driven refresh for real-time needs

3. **Concurrency**:
   - Thread-safe by design
   - No external locking needed
   - Safe for Django request handlers

---

## Testing

### Run All Tests

```bash
cd D:\Data\11_Backend\01_ARR\backend
python test_domain_manager.py
```

### Run Interactive Demo

```bash
python test_domain_manager.py --interactive
```

### Test Coverage

The test suite covers:
- ✅ Singleton pattern
- ✅ Domain retrieval (all, by ID, by name, by slug)
- ✅ Cache TTL and invalidation
- ✅ Change detection
- ✅ Event listeners
- ✅ Thread safety
- ✅ Performance benchmarks

---

## Troubleshooting

### Issue: "No domains found"

**Cause:** Neo4j database empty or Domain nodes not created

**Solution:**
```python
# Check Neo4j connection
from graph_db.services import Neo4jService
neo4j = Neo4jService()
neo4j.connect()

# Check for Domain nodes
result = neo4j.execute_query("MATCH (d:Domain) RETURN count(d) as count")
print(f"Domain count: {result[0]['count']}")

# If 0, run domain initialization
from agents.law.agent_manager import AgentManager
manager = AgentManager()  # Will auto-initialize domains
```

---

### Issue: "Cache not refreshing"

**Cause:** Auto-refresh disabled or TTL too high

**Solution:**
```python
# Force manual refresh
manager = DomainManager.get_instance()
stats = manager.refresh()
print(stats)

# Or invalidate and re-fetch
manager.invalidate_cache()
domains = manager.get_all_domains()
```

---

### Issue: "Thread safety errors"

**Cause:** External locking interfering with internal locks

**Solution:**
```python
# Don't use external locks - DomainManager is thread-safe
# ❌ Bad
with some_external_lock:
    domains = manager.get_all_domains()

# ✅ Good
domains = manager.get_all_domains()  # Already thread-safe
```

---

## Best Practices

### 1. Use Singleton Pattern

```python
# ✅ Good
manager = DomainManager.get_instance()

# ❌ Bad - creates multiple instances
manager1 = DomainManager()
manager2 = DomainManager()
```

### 2. Handle None Results

```python
# ✅ Good
domain = manager.get_domain(domain_id)
if domain:
    process(domain)
else:
    handle_not_found()

# ❌ Bad - may raise AttributeError
domain = manager.get_domain(domain_id)
process(domain.domain_name)  # Crashes if None
```

### 3. Use Change Listeners for Side Effects

```python
# ✅ Good - reactive
def on_domain_added(event):
    create_domain_agent(event.domain_id)

manager.add_change_listener(on_domain_added)

# ❌ Bad - polling
while True:
    domains = manager.get_all_domains()
    # Check for changes manually...
    time.sleep(10)
```

### 4. Choose Appropriate Cache TTL

```python
# Development (frequent changes)
DomainManager.get_instance(cache_ttl_seconds=30)

# Production (stable)
DomainManager.get_instance(cache_ttl_seconds=600)

# High-traffic read-heavy (aggressive caching)
DomainManager.get_instance(cache_ttl_seconds=3600)
```

---

## Integration Points

### AgentManager Integration

```python
from agents.law.agent_manager import AgentManager
from agents.law.domain_manager import DomainManager

class IntegratedAgentManager(AgentManager):
    def __init__(self):
        super().__init__()
        self.domain_manager = DomainManager.get_instance()

    def get_all_agent_metadata(self):
        """Get metadata for all agents"""
        return self.domain_manager.get_all_domains()
```

### QueryCoordinator Integration

```python
from agents.law.query_coordinator import QueryCoordinator
from agents.law.domain_manager import DomainManager

class EnhancedQueryCoordinator(QueryCoordinator):
    def __init__(self):
        super().__init__()
        self.domain_manager = DomainManager.get_instance()

        # Subscribe to domain changes
        self.domain_manager.add_change_listener(self._on_domain_change)

    def _on_domain_change(self, event):
        """React to domain changes"""
        if event.change_type.value == "added":
            self._register_new_agent(event.domain_id)
```

---

## Future Enhancements

Potential improvements for future versions:

1. **Async Support**: Async/await API for Django async views
2. **Metrics**: Prometheus/Grafana integration
3. **Distributed Cache**: Redis integration for multi-server setups
4. **Smart Refresh**: ML-based prediction of when to refresh
5. **GraphQL API**: GraphQL endpoint for domain queries

---

## References

- **Neo4j Service**: `D:\Data\11_Backend\01_ARR\backend\graph_db\services\neo4j_service.py`
- **AgentManager**: `D:\Data\11_Backend\01_ARR\backend\agents\law\agent_manager.py`
- **DomainAgent**: `D:\Data\11_Backend\01_ARR\backend\agents\law\domain_agent.py`
- **Test Suite**: `D:\Data\11_Backend\01_ARR\backend\test_domain_manager.py`

---

## License

Part of the ARR Law Search System. Internal use only.

---

**Last Updated**: 2025-01-17
**Version**: 1.0.0
**Author**: Claude Code Assistant
