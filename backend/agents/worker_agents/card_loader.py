"""
Agent Card Loader - JSON cards as source of truth

This utility loads agent cards from JSON files and provides caching.
JSON cards are the PRIMARY source, Django DB is just a query cache.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class AgentCardLoader:
    """
    Load and manage agent cards from JSON files

    Design principles:
    1. JSON cards are source of truth (not Django DB)
    2. Cards are cached in memory after first load
    3. URL field auto-generated if missing
    """

    CARDS_DIR = Path(__file__).parent / 'cards'
    _card_cache: Dict[str, dict] = {}
    _cache_loaded = False

    @classmethod
    def load_card(cls, agent_slug: str) -> dict:
        """
        Load a single agent card by slug

        Args:
            agent_slug: Agent slug (e.g., 'hostagent', 'flight-specialist')

        Returns:
            Agent card dictionary

        Raises:
            FileNotFoundError: If card file doesn't exist
        """
        # Check cache first
        if agent_slug in cls._card_cache:
            logger.debug(f"Agent card cache hit: {agent_slug}")
            return cls._card_cache[agent_slug]

        # Load from file
        card_path = cls.CARDS_DIR / f"{agent_slug}_card.json"

        if not card_path.exists():
            raise FileNotFoundError(
                f"Agent card not found: {card_path}\n"
                f"Available cards: {[f.stem.replace('_card', '') for f in cls.CARDS_DIR.glob('*_card.json')]}"
            )

        logger.info(f"Loading agent card from: {card_path}")

        with open(card_path, encoding='utf-8') as f:
            card = json.load(f)

        # Auto-generate URL if not present (A2A standard requires it)
        if 'url' not in card:
            base_url = getattr(settings, 'A2A_BASE_URL', 'http://localhost:8004')
            card['url'] = f"{base_url}/agents/{agent_slug}"
            logger.debug(f"Auto-generated URL for {agent_slug}: {card['url']}")

        # Cache it
        cls._card_cache[agent_slug] = card

        return card

    @classmethod
    def load_all_cards(cls) -> Dict[str, dict]:
        """
        Load all agent cards from cards directory

        Returns:
            Dictionary mapping agent_slug -> card_data
        """
        if cls._cache_loaded and cls._card_cache:
            logger.debug(f"Returning cached cards: {len(cls._card_cache)} agents")
            return cls._card_cache

        cards = {}
        card_files = list(cls.CARDS_DIR.glob('*_card.json'))

        logger.info(f"Loading {len(card_files)} agent cards from {cls.CARDS_DIR}")

        for card_file in card_files:
            # Extract slug from filename (flight_specialist_card.json -> flight_specialist)
            agent_slug_file = card_file.stem.replace('_card', '')

            # Normalize slug: replace underscore with hyphen for consistency
            # flight_specialist -> flight-specialist
            agent_slug = agent_slug_file.replace('_', '-')

            try:
                # Load using the original filename slug
                card = cls.load_card(agent_slug_file)

                # Store with normalized slug (hyphen-based) in both cards and cache
                cards[agent_slug] = card
                cls._card_cache[agent_slug] = card  # Also cache with normalized slug
                logger.debug(f"✓ Loaded: {agent_slug_file} as {agent_slug}")
            except Exception as e:
                logger.error(f"✗ Failed to load {agent_slug}: {e}")

        cls._cache_loaded = True
        logger.info(f"Successfully loaded {len(cards)} agent cards")

        return cards

    @classmethod
    def get_worker_class(cls, agent_slug: str) -> Optional[str]:
        """
        Get worker class name from agent card

        Args:
            agent_slug: Agent slug

        Returns:
            Worker class name from django.worker_class field, or None
        """
        try:
            card = cls.load_card(agent_slug)
            return card.get('django', {}).get('worker_class')
        except FileNotFoundError:
            logger.warning(f"No card found for agent: {agent_slug}")
            return None

    @classmethod
    def get_agent_skills(cls, agent_slug: str) -> list:
        """
        Get skills from agent card for semantic routing

        Args:
            agent_slug: Agent slug

        Returns:
            List of skill dictionaries with id, tags, examples
        """
        try:
            card = cls.load_card(agent_slug)
            return card.get('skills', [])
        except FileNotFoundError:
            logger.warning(f"No card found for agent: {agent_slug}")
            return []

    @classmethod
    def clear_cache(cls):
        """Clear the card cache (useful for testing or reload)"""
        logger.info("Clearing agent card cache")
        cls._card_cache.clear()
        cls._cache_loaded = False

    @classmethod
    def reload_card(cls, agent_slug: str) -> dict:
        """
        Force reload a specific card from disk

        Args:
            agent_slug: Agent slug to reload

        Returns:
            Reloaded card data
        """
        # Remove from cache
        if agent_slug in cls._card_cache:
            del cls._card_cache[agent_slug]

        # Reload from disk
        return cls.load_card(agent_slug)

    @classmethod
    def sync_to_database(cls):
        """
        Sync all JSON cards to Django Agent model

        This makes Django DB a cache for fast queries, admin UI, etc.
        JSON files remain the source of truth.
        """
        from agents.models import Agent
        from core.models import Organization
        from django.contrib.auth.models import User

        cards = cls.load_all_cards()
        synced_count = 0

        logger.info(f"Syncing {len(cards)} agent cards to Django database...")

        # Get or create default organization for system agents
        default_org, _ = Organization.objects.get_or_create(
            slug='system',
            defaults={'name': 'System', 'description': 'System-level agents from JSON cards'}
        )

        # Get or create system user for agent ownership
        system_user, _ = User.objects.get_or_create(
            username='system',
            defaults={'email': 'system@localhost', 'is_active': True}
        )

        for agent_slug, card in cards.items():
            try:
                # Get django config from card
                django_config = card.get('django', {})
                agent_type = django_config.get('agent_type', 'custom')

                # Get or create Agent model
                agent, created = Agent.objects.get_or_create(
                    organization=default_org,
                    slug=agent_slug,
                    defaults={
                        'name': card.get('name', agent_slug),
                        'agent_type': agent_type,
                        'created_by': system_user,
                        'model_name': django_config.get('model_config', {}).get('model_name', 'gpt-3.5-turbo')
                    }
                )

                # Update from card (even if already exists)
                agent.name = card.get('name', agent_slug)
                agent.description = card.get('description', '')

                # Store capabilities (A2A standard)
                capabilities_obj = card.get('capabilities', {})
                if isinstance(capabilities_obj, dict):
                    # Convert A2A capabilities object to list for Django
                    agent.capabilities = [
                        k for k, v in capabilities_obj.items() if v
                    ]
                else:
                    agent.capabilities = capabilities_obj

                # Store config from django section
                if django_config:
                    agent.config = django_config

                # Save
                agent.save()

                action = "Created" if created else "Updated"
                logger.info(f"  {action}: {agent_slug} - {agent.name}")
                synced_count += 1

            except Exception as e:
                logger.error(f"  Failed to sync {agent_slug}: {e}")

        logger.info(f"Database sync complete: {synced_count}/{len(cards)} agents synced")
        return synced_count


# Module-level convenience functions for backward compatibility
def load_agent_cards() -> Dict[str, dict]:
    """
    Convenience function to load all agent cards

    Returns:
        Dictionary mapping agent_slug -> card_data
    """
    return AgentCardLoader.load_all_cards()
