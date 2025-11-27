"""
DomainManager - Centralized Domain Discovery & Metadata Service

Responsibilities:
1. Query Neo4j for all Domain nodes
2. Cache domain list with periodic refresh
3. Provide domain metadata (domain_id, domain_name, description)
4. Detect when domains are added/removed
5. Serve as single source of truth for domain information

Design Pattern:
- Singleton pattern for global domain registry
- Cache-aside pattern with TTL-based invalidation
- Observer pattern for domain change notifications
"""

import logging
import threading
from typing import Dict, List, Optional, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from graph_db.services import Neo4jService

logger = logging.getLogger(__name__)


class DomainChangeType(Enum):
    """Domain change event types"""
    ADDED = "added"
    REMOVED = "removed"
    UPDATED = "updated"


@dataclass
class DomainMetadata:
    """
    Domain metadata container

    Represents a single domain with all its metadata.
    Immutable once created (use replace() for updates).
    """
    domain_id: str
    domain_name: str
    agent_slug: str
    node_count: int
    created_at: datetime
    updated_at: datetime
    centroid_embedding: Optional[List[float]] = None
    description: Optional[str] = None

    # Runtime metadata
    is_active: bool = True
    last_queried: Optional[datetime] = None
    query_count: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'domain_id': self.domain_id,
            'domain_name': self.domain_name,
            'agent_slug': self.agent_slug,
            'node_count': self.node_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'centroid_embedding': self.centroid_embedding,
            'description': self.description,
            'is_active': self.is_active,
            'last_queried': self.last_queried.isoformat() if self.last_queried else None,
            'query_count': self.query_count
        }

    @classmethod
    def from_neo4j_record(cls, record: Dict) -> 'DomainMetadata':
        """
        Create DomainMetadata from Neo4j query result

        Args:
            record: Neo4j query result record

        Returns:
            DomainMetadata instance
        """
        # Parse timestamps
        created_at = record.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        updated_at = record.get('updated_at')
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.now()

        return cls(
            domain_id=record['domain_id'],
            domain_name=record['domain_name'],
            agent_slug=record['agent_slug'],
            node_count=record.get('node_count', 0),
            created_at=created_at,
            updated_at=updated_at,
            centroid_embedding=record.get('centroid_embedding'),
            description=record.get('description')
        )


@dataclass
class DomainChangeEvent:
    """Domain change event for notifications"""
    change_type: DomainChangeType
    domain_id: str
    domain_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict] = None


class DomainManager:
    """
    Centralized Domain Manager

    Features:
    - Lazy loading: Loads domains from Neo4j on first access
    - Cache with TTL: Periodic refresh with configurable TTL
    - Change detection: Detects additions/removals
    - Thread-safe: Uses locks for concurrent access
    - Observable: Supports change event listeners

    Usage:
        # Get singleton instance
        manager = DomainManager.get_instance()

        # Get all domains
        domains = manager.get_all_domains()

        # Get specific domain
        domain = manager.get_domain("domain_abc123")

        # Force refresh
        manager.refresh()

        # Subscribe to changes
        manager.add_change_listener(lambda event: print(f"Domain changed: {event}"))
    """

    # Singleton instance
    _instance: Optional['DomainManager'] = None
    _lock = threading.Lock()

    # Cache configuration
    DEFAULT_CACHE_TTL_SECONDS = 300  # 5 minutes
    DEFAULT_AUTO_REFRESH_ENABLED = True

    def __init__(
        self,
        neo4j_service: Optional[Neo4jService] = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        auto_refresh: bool = DEFAULT_AUTO_REFRESH_ENABLED
    ):
        """
        Initialize DomainManager

        Args:
            neo4j_service: Neo4j service instance (or create new)
            cache_ttl_seconds: Cache time-to-live in seconds
            auto_refresh: Enable automatic cache refresh
        """
        self.neo4j = neo4j_service or Neo4jService()
        self.cache_ttl_seconds = cache_ttl_seconds
        self.auto_refresh = auto_refresh

        # Domain cache: domain_id -> DomainMetadata
        self._domains: Dict[str, DomainMetadata] = {}
        self._domain_ids: Set[str] = set()

        # Cache metadata
        self._last_refresh: Optional[datetime] = None
        self._is_cache_valid = False

        # Change tracking
        self._previous_domain_ids: Set[str] = set()
        self._change_listeners: List[Callable[[DomainChangeEvent], None]] = []

        # Thread safety
        self._cache_lock = threading.RLock()

        logger.info(
            f"DomainManager initialized: "
            f"cache_ttl={cache_ttl_seconds}s, auto_refresh={auto_refresh}"
        )

    @classmethod
    def get_instance(
        cls,
        neo4j_service: Optional[Neo4jService] = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        auto_refresh: bool = DEFAULT_AUTO_REFRESH_ENABLED
    ) -> 'DomainManager':
        """
        Get or create singleton instance

        Thread-safe singleton implementation.

        Args:
            neo4j_service: Neo4j service (only used on first call)
            cache_ttl_seconds: Cache TTL (only used on first call)
            auto_refresh: Auto refresh flag (only used on first call)

        Returns:
            DomainManager singleton instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(neo4j_service, cache_ttl_seconds, auto_refresh)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton instance (useful for testing)"""
        with cls._lock:
            cls._instance = None

    def get_all_domains(self, force_refresh: bool = False) -> List[DomainMetadata]:
        """
        Get all domains

        Returns cached domains if cache is valid, otherwise refreshes from Neo4j.

        Args:
            force_refresh: Force refresh from Neo4j regardless of cache validity

        Returns:
            List of DomainMetadata objects
        """
        with self._cache_lock:
            # Check cache validity
            if force_refresh or not self._is_cache_valid or self._is_cache_expired():
                logger.info("Cache invalid or expired, refreshing from Neo4j")
                self._refresh_from_neo4j()

            return list(self._domains.values())

    def get_domain(self, domain_id: str, force_refresh: bool = False) -> Optional[DomainMetadata]:
        """
        Get specific domain by ID

        Args:
            domain_id: Domain ID to retrieve
            force_refresh: Force refresh from Neo4j

        Returns:
            DomainMetadata or None if not found
        """
        with self._cache_lock:
            if force_refresh or not self._is_cache_valid or self._is_cache_expired():
                self._refresh_from_neo4j()

            domain = self._domains.get(domain_id)

            # Update query statistics
            if domain:
                domain.last_queried = datetime.now()
                domain.query_count += 1

            return domain

    def get_domain_by_name(self, domain_name: str, force_refresh: bool = False) -> Optional[DomainMetadata]:
        """
        Get domain by name

        Args:
            domain_name: Domain name to search for
            force_refresh: Force refresh from Neo4j

        Returns:
            DomainMetadata or None if not found
        """
        with self._cache_lock:
            if force_refresh or not self._is_cache_valid or self._is_cache_expired():
                self._refresh_from_neo4j()

            for domain in self._domains.values():
                if domain.domain_name == domain_name:
                    domain.last_queried = datetime.now()
                    domain.query_count += 1
                    return domain

            return None

    def get_domain_by_slug(self, agent_slug: str, force_refresh: bool = False) -> Optional[DomainMetadata]:
        """
        Get domain by agent slug

        Args:
            agent_slug: Agent slug to search for
            force_refresh: Force refresh from Neo4j

        Returns:
            DomainMetadata or None if not found
        """
        with self._cache_lock:
            if force_refresh or not self._is_cache_valid or self._is_cache_expired():
                self._refresh_from_neo4j()

            for domain in self._domains.values():
                if domain.agent_slug == agent_slug:
                    domain.last_queried = datetime.now()
                    domain.query_count += 1
                    return domain

            return None

    def refresh(self) -> Dict[str, any]:
        """
        Force refresh from Neo4j

        Returns:
            Refresh statistics
        """
        with self._cache_lock:
            logger.info("Manual refresh triggered")
            return self._refresh_from_neo4j()

    def invalidate_cache(self):
        """Invalidate cache (will refresh on next access)"""
        with self._cache_lock:
            self._is_cache_valid = False
            logger.info("Cache invalidated")

    def get_domain_count(self) -> int:
        """
        Get total domain count

        Returns:
            Number of domains
        """
        with self._cache_lock:
            if not self._is_cache_valid or self._is_cache_expired():
                self._refresh_from_neo4j()
            return len(self._domains)

    def get_active_domains(self) -> List[DomainMetadata]:
        """
        Get only active domains

        Returns:
            List of active DomainMetadata objects
        """
        return [d for d in self.get_all_domains() if d.is_active]

    def get_cache_info(self) -> Dict:
        """
        Get cache statistics

        Returns:
            Cache information dictionary
        """
        with self._cache_lock:
            return {
                'is_valid': self._is_cache_valid,
                'is_expired': self._is_cache_expired(),
                'last_refresh': self._last_refresh.isoformat() if self._last_refresh else None,
                'domain_count': len(self._domains),
                'cache_ttl_seconds': self.cache_ttl_seconds,
                'auto_refresh': self.auto_refresh,
                'listener_count': len(self._change_listeners)
            }

    def add_change_listener(self, listener: Callable[[DomainChangeEvent], None]):
        """
        Add domain change event listener

        Args:
            listener: Callback function that receives DomainChangeEvent
        """
        with self._cache_lock:
            self._change_listeners.append(listener)
            logger.info(f"Added change listener: {listener.__name__}")

    def remove_change_listener(self, listener: Callable[[DomainChangeEvent], None]):
        """
        Remove domain change event listener

        Args:
            listener: Callback function to remove
        """
        with self._cache_lock:
            if listener in self._change_listeners:
                self._change_listeners.remove(listener)
                logger.info(f"Removed change listener: {listener.__name__}")

    # ============== Private Methods ==============

    def _is_cache_expired(self) -> bool:
        """Check if cache has expired based on TTL"""
        if not self._last_refresh:
            return True

        age = datetime.now() - self._last_refresh
        return age.total_seconds() > self.cache_ttl_seconds

    def _refresh_from_neo4j(self) -> Dict[str, any]:
        """
        Refresh domain cache from Neo4j

        Returns:
            Refresh statistics
        """
        try:
            start_time = datetime.now()

            # Ensure Neo4j connection
            if not self.neo4j._driver:
                self.neo4j.connect()

            # Query all Domain nodes
            query = """
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
            """

            results = self.neo4j.execute_query(query, {})

            # Build new domain cache
            new_domains = {}
            new_domain_ids = set()

            for record in results:
                domain_metadata = DomainMetadata.from_neo4j_record(record)

                # Use actual count if available
                if record.get('actual_node_count') is not None:
                    domain_metadata.node_count = record['actual_node_count']

                new_domains[domain_metadata.domain_id] = domain_metadata
                new_domain_ids.add(domain_metadata.domain_id)

            # Detect changes
            added_ids = new_domain_ids - self._previous_domain_ids
            removed_ids = self._previous_domain_ids - new_domain_ids

            # Update cache
            old_domain_count = len(self._domains)
            self._domains = new_domains
            self._domain_ids = new_domain_ids
            self._last_refresh = datetime.now()
            self._is_cache_valid = True

            # Fire change events
            self._fire_change_events(added_ids, removed_ids, new_domains)

            # Update previous state for next comparison
            self._previous_domain_ids = new_domain_ids.copy()

            # Statistics
            duration = (datetime.now() - start_time).total_seconds()
            stats = {
                'success': True,
                'domain_count': len(new_domains),
                'domains_added': len(added_ids),
                'domains_removed': len(removed_ids),
                'previous_count': old_domain_count,
                'duration_seconds': duration,
                'timestamp': datetime.now().isoformat()
            }

            logger.info(
                f"Domain cache refreshed: {stats['domain_count']} domains, "
                f"+{stats['domains_added']} -{stats['domains_removed']}, "
                f"{duration:.3f}s"
            )

            return stats

        except Exception as e:
            logger.error(f"Failed to refresh domain cache from Neo4j: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def _fire_change_events(
        self,
        added_ids: Set[str],
        removed_ids: Set[str],
        current_domains: Dict[str, DomainMetadata]
    ):
        """
        Fire change events to listeners

        Args:
            added_ids: Set of newly added domain IDs
            removed_ids: Set of removed domain IDs
            current_domains: Current domain cache
        """
        if not self._change_listeners:
            return

        # Fire ADDED events
        for domain_id in added_ids:
            domain = current_domains.get(domain_id)
            if domain:
                event = DomainChangeEvent(
                    change_type=DomainChangeType.ADDED,
                    domain_id=domain_id,
                    domain_name=domain.domain_name,
                    metadata=domain.to_dict()
                )
                self._notify_listeners(event)

        # Fire REMOVED events
        for domain_id in removed_ids:
            # Get domain name from previous cache if available
            old_domain = self._domains.get(domain_id)
            domain_name = old_domain.domain_name if old_domain else domain_id

            event = DomainChangeEvent(
                change_type=DomainChangeType.REMOVED,
                domain_id=domain_id,
                domain_name=domain_name
            )
            self._notify_listeners(event)

    def _notify_listeners(self, event: DomainChangeEvent):
        """
        Notify all listeners of a change event

        Args:
            event: DomainChangeEvent to broadcast
        """
        for listener in self._change_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(
                    f"Error in change listener {listener.__name__}: {e}",
                    exc_info=True
                )


# ============== Helper Functions ==============

def get_domain_manager(
    neo4j_service: Optional[Neo4jService] = None,
    cache_ttl_seconds: int = DomainManager.DEFAULT_CACHE_TTL_SECONDS,
    auto_refresh: bool = DomainManager.DEFAULT_AUTO_REFRESH_ENABLED
) -> DomainManager:
    """
    Convenience function to get DomainManager singleton

    Args:
        neo4j_service: Neo4j service instance
        cache_ttl_seconds: Cache TTL in seconds
        auto_refresh: Enable auto refresh

    Returns:
        DomainManager instance
    """
    return DomainManager.get_instance(neo4j_service, cache_ttl_seconds, auto_refresh)


def create_domain_lookup_dict(domains: List[DomainMetadata]) -> Dict[str, DomainMetadata]:
    """
    Create lookup dictionary from domain list

    Args:
        domains: List of DomainMetadata

    Returns:
        Dict mapping domain_id to DomainMetadata
    """
    return {d.domain_id: d for d in domains}


# ============== Example Usage ==============

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Example 1: Get singleton instance
    manager = DomainManager.get_instance()

    # Example 2: Get all domains
    print("\n=== All Domains ===")
    all_domains = manager.get_all_domains()
    for domain in all_domains:
        print(f"- {domain.domain_name} ({domain.domain_id}): {domain.node_count} nodes")

    # Example 3: Get specific domain
    print("\n=== Get Specific Domain ===")
    if all_domains:
        first_domain_id = all_domains[0].domain_id
        domain = manager.get_domain(first_domain_id)
        if domain:
            print(f"Found: {domain.domain_name}")
            print(f"  Agent slug: {domain.agent_slug}")
            print(f"  Node count: {domain.node_count}")
            print(f"  Created: {domain.created_at}")

    # Example 4: Add change listener
    print("\n=== Change Listener ===")
    def on_domain_change(event: DomainChangeEvent):
        print(f"Domain {event.change_type.value}: {event.domain_name} (ID: {event.domain_id})")

    manager.add_change_listener(on_domain_change)

    # Example 5: Force refresh (will detect changes)
    print("\n=== Force Refresh ===")
    stats = manager.refresh()
    print(f"Refresh stats: {stats}")

    # Example 6: Cache info
    print("\n=== Cache Info ===")
    cache_info = manager.get_cache_info()
    for key, value in cache_info.items():
        print(f"  {key}: {value}")
